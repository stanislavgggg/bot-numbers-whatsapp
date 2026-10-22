"""End-to-end dialog test with a fake Telegram session (no network, no token needed)."""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.methods import TelegramMethod  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update, User  # noqa: E402

import bot as botmod  # noqa: E402
from config import Config  # noqa: E402
from db import Database  # noqa: E402


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _detach_router():
    """The module-level router can be attached to one Dispatcher at a time; every test builds its own."""
    botmod.router._parent_router = None
    yield
    botmod.router._parent_router = None


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent: list[tuple[str, dict]] = []

    async def close(self): ...
    async def stream_content(self, *a, **k): ...

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        self.sent.append((type(method).__name__, method.model_dump(exclude_none=True)))
        name = type(method).__name__
        if name in ("SendMessage", "SendDocument"):
            return Message(message_id=len(self.sent), date=datetime.now(),
                           chat=Chat(id=1, type="private"), text="x")
        return True


USER = User(id=42, is_bot=False, first_name="Stan", username="stan")
CHAT = Chat(id=42, type="private")


def msg(i, text=None, contact=None):
    return Update(update_id=i, message=Message(message_id=i, date=datetime.now(), chat=CHAT,
                                               from_user=USER, text=text, contact=contact))


def cbq(i, data):
    m = Message(message_id=100 + i, date=datetime.now(), chat=CHAT, text="x", from_user=User(id=1, is_bot=True, first_name="bot"))
    return Update(update_id=i, callback_query=CallbackQuery(id=str(i), from_user=USER, chat_instance="c", message=m, data=data))


def test_full_flow(tmp_path):
    async def run():
        cfg = Config(bot_token="1:x", admin_ids={42}, privacy_url="https://example.com/privacy",
                     channel_url="https://t.me/example", db_path=str(tmp_path / "f.db"))
        db = Database(cfg.db_path)
        session = FakeSession()
        bot = Bot("1:AAA", session=session)
        dp = Dispatcher(storage=MemoryStorage(), cfg=cfg, db=db)
        dp.include_router(botmod.router)

        async def feed(u): await dp.feed_update(bot, u)

        await feed(msg(1, "/start A1"))
        # the disclaimer must name WhatsApp explicitly and offer the explicit opt-in button
        welcome = session.sent[0][1]
        assert "WhatsApp" in welcome["text"] and "acepto" in welcome["text"].lower()
        # short mode keeps only what makes the tap meaningful: sender, WhatsApp, opt-out, 18+, privacy link
        assert "Apuestas Guru" in welcome["text"] and "/borrar" in welcome["text"] and "+18" in welcome["text"]
        assert "Ningún pronóstico garantiza" not in welcome["text"]
        assert "https://example.com/privacy" in welcome["text"]
        assert "Tengo 18+ y acepto" in str(welcome["reply_markup"])
        # offer part: what is inside + free/no-card line; no invented sample pick any more
        assert "Qué apostar, a qué cuota y por qué" in welcome["text"] and "sin tarjeta" in welcome["text"]
        assert "Equipo A" not in welcome["text"]
        # CTA, then "see the channel" (check before giving a number), then "No"; trust lines only when configured
        kb = welcome["reply_markup"]["inline_keyboard"]
        assert len(kb) == 3 and "canal" in kb[1][0]["text"] and kb[1][0]["url"] == "https://t.me/example"
        assert "👥" not in welcome["text"]
        # nothing is stored before the number is given
        assert (await db.stats())["total"] == 0

        await feed(cbq(2, "age:yes"))
        await feed(msg(4, "123"))                    # invalid -> asks again
        assert any("no parece válido" in str(d.get("text", "")) for _, d in session.sent)
        assert (await db.stats())["total"] == 0
        await feed(msg(5, "612 345 678"))            # valid -> saved, club question is optional
        done = [d for n, d in session.sent if n == "SendMessage" and "Listo" in str(d.get("text", ""))][-1]
        assert "Apuestas Guru" in done["text"] and "WhatsApp" in done["text"]      # sender is named
        club_msg = [d for n, d in session.sent if n == "SendMessage" and "Opcional" in str(d.get("text", ""))][-1]
        kb = club_msg["reply_markup"]["inline_keyboard"]
        assert "https://t.me/example" in str(kb)     # channel link is visible even if the club is never picked
        assert sum(1 for row in kb for b in row if str(b.get("callback_data", "")).startswith("club:")) == 4
        await feed(cbq(6, "club:fcb"))

        s = await db.stats()
        assert s["total"] == 1
        assert dict(s["by_payload"]) == {"A1": 1}
        assert dict(s["by_club"]) == {"Barça": 1}
        lead = (await db.all_leads())[0]
        assert lead["phone"] == "+34612345678" and lead["consent"] == 1 and lead["age_confirmed"] == 1
        assert lead["consent_version"] == "es-tg-v4-short" and lead["consent_at"]

        # someone else's contact must be rejected
        await feed(msg(7, "/start"))
        await feed(cbq(8, "age:yes"))
        await feed(msg(10, contact=Contact(phone_number="34699999999", first_name="X", user_id=999)))
        assert any("tu propio número" in str(d.get("text", "")) for _, d in session.sent)

        # admin commands
        await feed(msg(11, "/stats"))
        await feed(msg(12, "/export"))
        assert any(n == "SendDocument" for n, _ in session.sent)

        # delete my data
        await feed(cbq(13, "del:yes"))
        assert (await db.stats())["total"] == 0

    asyncio.run(run())


def test_trust_extra_optional_and_escaped():
    base = Config(bot_token="1:x")
    assert botmod.trust_extra(base) == ""
    cfg = Config(bot_token="1:x", frequency_line="Máximo 3 mensajes por semana", proof_line="R&D <b>fans</b>")
    extra = botmod.trust_extra(cfg)
    assert "✅ Máximo 3 mensajes por semana" in extra
    assert "&amp;" in extra and "&lt;b&gt;" in extra       # env text can never break Telegram HTML
    assert extra.startswith("\n")
    text = botmod.welcome_text(cfg)
    assert "Máximo 3 mensajes por semana" in text and "{trust_extra}" not in text


def test_welcome_has_balanced_html_tags():
    import re
    text = botmod.welcome_text(Config(bot_token="1:x", privacy_url="https://example.com/p",
                                       frequency_line="Poco spam", proof_line="Mucha gente"))
    for tag in ("b", "i", "blockquote", "a"):
        assert len(re.findall(rf"<{tag}[ >]", text)) == len(re.findall(rf"</{tag}>", text)), tag
    assert len(text) < 3500   # Telegram hard limit is 4096


def _setup(tmp_path, **kw):
    cfg = Config(bot_token="1:x", admin_ids={42}, db_path=str(tmp_path / "x.db"), **kw)
    db = Database(cfg.db_path)
    session = FakeSession()
    bot = Bot("1:AAA", session=session)
    dp = Dispatcher(storage=MemoryStorage(), cfg=cfg, db=db)
    dp.include_router(botmod.router)
    return cfg, db, session, bot, dp


def test_payload_is_sanitized_and_stats_survive(tmp_path):
    async def run():
        cfg, db, session, bot, dp = _setup(tmp_path)
        feed = lambda u: dp.feed_update(bot, u)
        await feed(msg(1, "/start <b>evil</b>&x"))
        await feed(cbq(2, "age:yes"))
        await feed(msg(3, "612 345 678"))
        lead = (await db.all_leads())[0]
        assert lead["payload"] == "bevilbx"                  # only A-Za-z0-9_- survive
        assert botmod.clean_payload("A1__spring__k" + "x" * 80) .startswith("A1__spring__k") \
            and len(botmod.clean_payload("x" * 80)) == 64
        await feed(msg(4, "/stats"))                         # must not raise on HTML parsing
    asyncio.run(run())


def test_brand_is_html_escaped_in_messages(tmp_path):
    cfg = Config(bot_token="1:x", brand_name="Guru & Co <b>")
    assert "Guru &amp; Co &lt;b&gt;" in botmod.welcome_text(cfg)
    assert botmod.brand_name(cfg) == "Guru &amp; Co &lt;b&gt;"
    assert cfg.brand_name == "Guru & Co <b>"                 # the sheet still gets the raw name


def test_double_tap_and_non_text_while_waiting_for_number(tmp_path):
    async def run():
        cfg, db, session, bot, dp = _setup(tmp_path)
        feed = lambda u: dp.feed_update(bot, u)
        await feed(msg(1, "/start"))
        await feed(cbq(2, "age:yes"))
        asks = lambda: sum("Solo falta tu número" in str(d.get("text", "")) for _, d in session.sent)
        assert asks() == 1
        await feed(cbq(3, "age:yes"))                        # second tap: no second prompt
        assert asks() == 1
        await feed(msg(4))                                   # sticker/photo: asks for the number again
        assert asks() == 2
        assert not any(d.get("text") == botmod.T.FALLBACK for _, d in session.sent)
        await feed(msg(5, "612 345 678"))
        assert (await db.stats())["total"] == 1
    asyncio.run(run())


def test_stale_club_button_after_delete(tmp_path):
    async def run():
        cfg, db, session, bot, dp = _setup(tmp_path)
        feed = lambda u: dp.feed_update(bot, u)
        await feed(msg(1, "/start"))
        await feed(cbq(2, "age:yes"))
        await feed(msg(3, "612 345 678"))
        await feed(cbq(4, "del:yes"))
        await feed(cbq(5, "club:rm"))                        # old button after /borrar: no crash, nothing stored
        assert (await db.stats())["total"] == 0
    asyncio.run(run())


def test_csv_formula_injection_is_neutralised():
    assert botmod.csv_safe("first_name", '=HYPERLINK("http://x","y")').startswith("'=")
    assert botmod.csv_safe("first_name", "@SUM(A1)") == "'@SUM(A1)"
    assert botmod.csv_safe("first_name", "-2+3") == "'-2+3"
    assert botmod.csv_safe("first_name", "Stan") == "Stan"
    assert botmod.csv_safe("phone", "+34612345678") == "+34612345678"   # validated E.164 stays as is
    assert botmod.csv_safe("consent", 1) == 1


def test_full_disclaimer_mode_keeps_the_legal_block(tmp_path):
    async def run():
        cfg, db, session, bot, dp = _setup(tmp_path, privacy_url="https://example.com/privacy", disclaimer="full")
        feed = lambda u: dp.feed_update(bot, u)
        await feed(msg(1, "/start"))
        text = session.sent[0][1]["text"]
        assert "Ningún pronóstico garantiza un resultado" in text and "mayores de 18" in text
        assert "ejemplo ilustrativo" in text and "https://example.com/privacy" in text
        await feed(cbq(2, "age:yes"))
        await feed(msg(3, "612 345 678"))
        assert (await db.all_leads())[0]["consent_version"] == "es-tg-v3"        # the version records what was shown
        assert any("Juega con responsabilidad" in str(d.get("text", "")) for _, d in session.sent)
    asyncio.run(run())


def test_short_mode_is_much_lighter_than_full():
    short = botmod.welcome_text(Config(bot_token="1:x", privacy_url="https://e.com/p"))
    full = botmod.welcome_text(Config(bot_token="1:x", privacy_url="https://e.com/p", disclaimer="full"))
    assert len(short) < len(full) - 150
    import re
    for tag in ("b", "i", "blockquote", "a"):
        assert len(re.findall(rf"<{tag}[ >]", short)) == len(re.findall(rf"</{tag}>", short)), tag


def test_real_proof_lines_and_channel_button():
    cfg = Config(bot_token="1:x", proof_line="+2.800 aficionados en Telegram",
                 results_line="Octubre en el canal: 15 aciertos y 4 fallos publicados, balance +572 € (declarado, no auditado)")
    text = botmod.welcome_text(cfg)
    assert "📊 Octubre en el canal: 15 aciertos y 4 fallos" in text and "no auditado" in text
    assert "👥 +2.800 aficionados en Telegram" in text
    assert text.index("📊") < text.index("👥") < text.index("✅ Gratis")     # proof first, then the free line, consent last
    assert text.index("✅ Gratis") < text.index("Al pulsar")
    assert len(botmod.kb_age(Config(bot_token="1:x")).inline_keyboard) == 2   # no channel url, no extra button
    assert len(botmod.kb_age(Config(bot_token="1:x", channel_url="https://t.me/c")).inline_keyboard) == 3


def test_bonus_block_only_when_url_set(tmp_path):
    async def run():
        for url, expected in (("", False), ("https://t.me/ApuestasGuruES/123", True)):
            botmod.router._parent_router = None
            cfg, db, session, bot, dp = _setup(tmp_path, bonus_url=url)
            feed = lambda u: dp.feed_update(bot, u)
            await feed(msg(1, "/start"))
            await feed(cbq(2, "age:yes"))
            await feed(msg(3, "612 345 678"))
            done = [d["text"] for n, d in session.sent if n == "SendMessage" and "Listo" in str(d.get("text", ""))][-1]
            assert ("CaptainsBet" in done) is expected
            if expected:
                # separated from the free pack, conditions visible, link present, still before the optional club question
                assert "Oferta aparte" in done and "100% extra hasta 100 €" in done
                assert "Rollover x5" in done and "3 días" in done and "El pack sigue siendo gratis" in done
                assert url in done
            (tmp_path / "x.db").unlink(missing_ok=True)
    asyncio.run(run())
