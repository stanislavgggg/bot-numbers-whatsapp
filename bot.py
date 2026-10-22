import asyncio
import contextlib
import csv
import html
import io
import logging
import os
import re
from datetime import datetime, timezone

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LinkPreviewOptions,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import texts as T
from config import Config, load_config
from db import COLUMNS, Database
from phone import normalize_phone, pretty_phone
from sheets import SheetSink

log = logging.getLogger("leadbot")
router = Router()


class Flow(StatesGroup):
    phone = State()


_tasks: set[asyncio.Task] = set()


def spawn(coro) -> asyncio.Task:
    """create_task that keeps a strong reference (the event loop only holds weak ones, so a task can vanish mid-flight)."""
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return t


def clean_payload(raw: str | None) -> str:
    """Deep-link tag: only A-Za-z0-9_- (what Telegram itself allows), max 64. Typed '/start <b>x' cannot break HTML or the sheet."""
    return re.sub(r"[^A-Za-z0-9_-]", "", raw or "")[:64]


def csv_safe(col: str, value):
    """Stop spreadsheet formula injection in /export (a Telegram first_name can be '=HYPERLINK(...)'). Phone is validated E.164."""
    if col != "phone" and isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


# ---------- keyboards ----------
def kb_age() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=T.BTN_AGE_YES, callback_data="age:yes")],
        [InlineKeyboardButton(text=T.BTN_AGE_NO, callback_data="age:no")],
    ])


def kb_clubs(cfg: Config | None = None) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=name, callback_data=f"club:{key}") for key, name in T.CLUBS.items()]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    if cfg is not None and cfg.channel_url:
        rows.append([InlineKeyboardButton(text=T.BTN_CHANNEL, url=cfg.channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_channel(cfg: Config) -> InlineKeyboardMarkup | None:
    if not cfg.channel_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=T.BTN_CHANNEL, url=cfg.channel_url)]])


def kb_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=T.BTN_SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ---------- helpers ----------
def welcome_text(cfg: Config) -> str:
    privacy = T.PRIVACY_LINE.format(url=html.escape(cfg.privacy_url, quote=True)) if cfg.privacy_url else ""
    return T.WELCOME.format(brand=brand_name(cfg), privacy=privacy, trust_extra=trust_extra(cfg))


def brand_name(cfg: Config) -> str:
    """HTML-escaped: used only inside Telegram HTML messages (a bare '&' or '<' would make Telegram reject the message)."""
    return html.escape(cfg.brand_name or T.BRAND_FALLBACK, quote=False)


def trust_extra(cfg: Config) -> str:
    """Optional trust lines (message frequency, social proof). Empty unless set in env; escaped for HTML."""
    lines = []
    if cfg.frequency_line:
        lines.append("✅ " + html.escape(cfg.frequency_line, quote=False))
    if cfg.proof_line:
        lines.append("👥 " + html.escape(cfg.proof_line, quote=False))
    return "".join("\n" + x for x in lines)


async def post_webhook(cfg: Config, lead: dict) -> None:
    """Fires once when the number is saved and again if the user picks a club (dedupe by tg_id)."""
    if not cfg.webhook_url:
        return
    headers = {"X-Webhook-Secret": cfg.webhook_secret} if cfg.webhook_secret else {}
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(cfg.webhook_url, json=lead, headers=headers) as r:
                if r.status >= 400:
                    log.warning("webhook returned %s", r.status)
    except Exception as e:  # never break the user flow because of the webhook
        log.warning("webhook failed: %s", e)


async def ask_phone(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.phone)
    await message.answer(T.ASK_PHONE, reply_markup=kb_phone())


async def save_phone(message: Message, state: FSMContext, cfg: Config, db: Database, raw: str) -> None:
    e164 = normalize_phone(raw, cfg.default_region)
    if not e164:
        await message.answer(T.BAD_PHONE)
        return
    data = await state.get_data()
    u = message.from_user
    lead = await db.save_lead(
        tg_id=u.id,
        username=u.username,
        first_name=u.first_name,
        payload=data.get("payload", ""),
        club=None,
        phone=e164,
        consent_at=data.get("consent_at"),
        consent_version=T.CONSENT_VERSION,
    )
    spawn(post_webhook(cfg, lead))
    await state.clear()
    await message.answer(T.DONE.format(phone=pretty_phone(e164), brand=brand_name(cfg)),
                         reply_markup=ReplyKeyboardRemove())
    await message.answer(T.ASK_CLUB, reply_markup=kb_clubs(cfg))


# ---------- user flow ----------
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, cfg: Config):
    await state.clear()
    await state.update_data(payload=clean_payload(command.args))
    await message.answer(welcome_text(cfg), reply_markup=kb_age(),
                         link_preview_options=LinkPreviewOptions(is_disabled=True))


@router.callback_query(F.data == "age:no")
async def age_no(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(T.UNDERAGE)
    await cb.answer()


@router.callback_query(F.data == "age:yes")
async def accept(cb: CallbackQuery, state: FSMContext):
    if await state.get_state() == Flow.phone.state:  # double tap: already asked, keep the first consent time
        await cb.answer()
        return
    # Explicit opt-in: the tap is the consent; its time is stored with the lead.
    await state.update_data(consent_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with contextlib.suppress(TelegramBadRequest):
        await cb.message.edit_reply_markup(reply_markup=None)
    await ask_phone(cb.message, state)
    await cb.answer()


@router.message(Flow.phone, F.contact)
async def phone_contact(message: Message, state: FSMContext, cfg: Config, db: Database):
    if message.contact.user_id != message.from_user.id:
        await message.answer(T.NOT_OWN_CONTACT)
        return
    await save_phone(message, state, cfg, db, message.contact.phone_number)


@router.message(Flow.phone, F.text & ~F.text.startswith("/"))
async def phone_text(message: Message, state: FSMContext, cfg: Config, db: Database):
    await save_phone(message, state, cfg, db, message.text)


@router.message(Flow.phone, ~F.text)
async def phone_other(message: Message):
    await message.answer(T.ASK_PHONE, reply_markup=kb_phone())


@router.callback_query(F.data.startswith("club:"))
async def club_chosen(cb: CallbackQuery, cfg: Config, db: Database):
    name = T.CLUBS.get(cb.data.split(":", 1)[1], "Otro equipo")
    lead = await db.set_club(cb.from_user.id, name)
    if not lead:  # data was deleted with /borrar, or an old button
        await cb.message.edit_text(T.FALLBACK)
        await cb.answer()
        return
    spawn(post_webhook(cfg, lead))
    await cb.message.edit_text(T.CLUB_THANKS.format(club=name), reply_markup=kb_channel(cfg))
    await cb.answer()


# ---------- GDPR: delete my data ----------
@router.message(Command("borrar", "stop", "delete"))
async def cmd_delete(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=T.BTN_DEL_YES, callback_data="del:yes"),
        InlineKeyboardButton(text=T.BTN_DEL_NO, callback_data="del:no"),
    ]])
    await message.answer(T.DELETE_ASK, reply_markup=kb)


@router.callback_query(F.data == "del:yes")
async def delete_yes(cb: CallbackQuery, db: Database):
    lead = await db.delete(cb.from_user.id)  # its sheet row is removed by the sync worker
    await cb.message.edit_text(T.DELETED if lead else T.NOTHING_TO_DELETE)
    await cb.answer()


@router.callback_query(F.data == "del:no")
async def delete_no(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer()


# ---------- admin ----------
def _is_admin(message: Message, cfg: Config) -> bool:
    return message.from_user is not None and message.from_user.id in cfg.admin_ids


@router.message(Command("stats"))
async def cmd_stats(message: Message, cfg: Config, db: Database):
    if not _is_admin(message, cfg):
        return
    s = await db.stats()
    lines = [f"📊 <b>Leads</b>: {s['total']} (últimas 24 h: {s['last_24h']})", "", "<b>Por tag (?start=…)</b>"]
    lines += [f"• {html.escape(str(p), quote=False)}: {n}" for p, n in s["by_payload"]] or ["—"]
    lines += ["", "<b>Por equipo</b>"]
    lines += [f"• {html.escape(str(k), quote=False)}: {n}" for k, n in s["by_club"]] or ["—"]
    await message.answer("\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message, cfg: Config, db: Database):
    if not _is_admin(message, cfg):
        return
    rows = await db.all_leads()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")  # skip internal rev/synced
    w.writeheader()
    w.writerows([{k: csv_safe(k, v) for k, v in r.items()} for r in rows])
    data = buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens UTF-8 correctly
    await message.answer_document(BufferedInputFile(data, filename="leads.csv"), caption=f"{len(rows)} leads")


# ---------- fallback (must stay last) ----------
@router.message()
async def fallback(message: Message):
    await message.answer(T.FALLBACK)


async def sync_loop(cfg: Config, db: Database, sink: SheetSink) -> None:
    """Every few seconds push new/changed leads to the Google Sheet in one batch (idempotent, retries on failure)."""
    while True:
        try:
            leads = await db.unsynced()
            deletes = await db.pending_deletes()
            if leads or deletes:
                await asyncio.to_thread(sink.sync, leads, deletes)
                await db.mark_synced([(x["tg_id"], x["rev"]) for x in leads])
                await db.clear_pending(deletes)
        except Exception:
            log.exception("sheet sync failed, will retry")
        await asyncio.sleep(cfg.sync_interval)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    if os.environ.get("RENDER") and not os.path.ismount(os.path.dirname(os.path.abspath(cfg.db_path))):
        log.warning("DB_PATH=%s is not on a persistent disk: SQLite is wiped on every deploy/restart "
                    "(attach a Disk and set DB_PATH=/var/data/leads.db)", cfg.db_path)
    db = Database(cfg.db_path)
    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage(), cfg=cfg, db=db)
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=False)
    username = (await bot.get_me()).username
    log.info("bot started as @%s", username)
    if cfg.gsheet_id and cfg.google_sa_json:
        # fail loudly at startup if the sheet is not reachable / not shared with the service account
        sink = await asyncio.to_thread(SheetSink.connect, cfg, username)
        spawn(sync_loop(cfg, db, sink))
        log.info("Google Sheets sync enabled")
    else:
        log.warning("GSHEET_ID / GOOGLE_SERVICE_ACCOUNT_JSON not set: leads are stored in SQLite only")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
