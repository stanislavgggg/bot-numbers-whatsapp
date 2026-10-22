"""Batched, idempotent sync of leads into the "Quiz leads" Google Sheet.

Rows are matched by lead_id (column B), so a retry never creates duplicates, a club update
rewrites the same row, and /borrar removes it. Columns are filled by header name, so adding or
reordering columns in the sheet does not break anything.
"""
import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import phonenumbers
from gspread.utils import rowcol_to_a1

from config import Config

log = logging.getLogger("leadbot.sheets")

# Columns of the existing sheet (see Quiz_leads_Oct_2026)
HEADERS = [
    "timestamp", "lead_id", "quiz_id", "geo", "club", "email", "phone", "whatsapp_consent",
    "favourite_team", "bet_frequency", "answers_json", "consent", "consent_text_version",
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid",
    "brand", "landing_url", "referrer",
]

# Same style of values the web quizzes already write (barca, real_madrid, other)
CLUB_CODES = {
    "Real Madrid": "real_madrid",
    "Barça": "barca",
    "Atlético de Madrid": "atletico_madrid",
    "Otro equipo": "other",
}


def _fmt_ts(iso: str, tz: str) -> str:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz)).strftime("%d/%m/%Y %H:%M:%S")


def _geo(e164: str, fallback: str) -> str:
    try:
        return phonenumbers.region_code_for_number(phonenumbers.parse(e164, None)) or fallback
    except phonenumbers.NumberParseException:
        return fallback


def split_payload(payload: str) -> tuple[str, str, str]:
    """?start=campaign__content__term  ->  (utm_campaign, utm_content, utm_term).
    A single token (?start=A1) is treated as the creative tag, i.e. utm_content."""
    payload = (payload or "").strip()
    if not payload:
        return "", "", ""
    if "__" not in payload:
        return "", payload, ""
    parts = (payload.split("__") + ["", ""])[:3]
    return parts[0], parts[1], parts[2]


def lead_to_row(lead: dict, cfg: Config, bot_username: str = "") -> dict:
    club = CLUB_CODES.get(lead.get("club") or "", "")
    campaign, content, term = split_payload(lead.get("payload") or "")
    answers = {"flow": "telegram_bot"}
    if club:
        answers["club"] = club
    landing = f"https://t.me/{bot_username}" if bot_username else ""
    if landing and lead.get("payload"):
        landing += f"?start={lead['payload']}"
    return {
        "timestamp": _fmt_ts(lead["created_at"], cfg.sheet_tz),
        "lead_id": lead["lead_id"],
        "quiz_id": cfg.quiz_id,
        "geo": _geo(lead["phone"], cfg.default_region),
        "club": club,
        "email": "",
        "phone": lead["phone"].lstrip("+"),   # digits only, like most existing rows (34612345678)
        "whatsapp_consent": bool(lead.get("consent")),
        "favourite_team": club,
        "bet_frequency": "",
        "answers_json": json.dumps(answers, ensure_ascii=False),
        "consent": bool(lead.get("consent")),
        "consent_text_version": lead.get("consent_version") or "",
        "utm_source": cfg.utm_source,
        "utm_medium": cfg.utm_medium,
        "utm_campaign": campaign,
        "utm_content": content,
        "utm_term": term,
        "fbclid": "",
        "brand": cfg.brand_name,
        "landing_url": landing,
        "referrer": "telegram",
    }


class SheetSink:
    def __init__(self, ws, cfg: Config, bot_username: str = ""):
        self.ws = ws
        self.cfg = cfg
        self.bot_username = bot_username
        self.headers = ws.row_values(1)
        if "lead_id" not in self.headers:
            raise RuntimeError("The sheet has no 'lead_id' column in row 1; cannot sync safely")
        missing = [h for h in HEADERS if h not in self.headers]
        if missing:
            log.warning("sheet is missing columns (they will be skipped): %s", missing)

    @classmethod
    def connect(cls, cfg: Config, bot_username: str = "") -> "SheetSink":
        import gspread  # imported lazily so tests and SQLite-only mode do not need credentials

        gc = gspread.service_account_from_dict(json.loads(cfg.google_sa_json))
        sh = gc.open_by_key(cfg.gsheet_id)
        ws = sh.get_worksheet_by_id(int(cfg.gsheet_gid)) if cfg.gsheet_gid else sh.sheet1
        return cls(ws, cfg, bot_username)

    def _values(self, row: dict) -> list:
        return [row.get(h, "") for h in self.headers]

    def sync(self, leads: list[dict], delete_ids: list[str]) -> None:
        id_col = self.headers.index("lead_id") + 1
        existing = {v: i for i, v in enumerate(self.ws.col_values(id_col), start=1) if v and i > 1}
        last_col = len(self.headers)

        updates, appends = [], []
        for lead in leads:
            vals = self._values(lead_to_row(lead, self.cfg, self.bot_username))
            r = existing.get(lead["lead_id"])
            if r:
                updates.append({"range": f"{rowcol_to_a1(r, 1)}:{rowcol_to_a1(r, last_col)}", "values": [vals]})
            else:
                appends.append(vals)
        if updates:
            self.ws.batch_update(updates, value_input_option="RAW")
        if appends:
            self.ws.append_rows(appends, value_input_option="RAW", table_range="A1")

        # delete bottom-up so earlier row numbers stay valid
        rows = sorted({existing[i] for i in delete_ids if i in existing}, reverse=True)
        for r in rows:
            self.ws.delete_rows(r)
        log.info("sheet sync: %d updated, %d appended, %d deleted", len(updates), len(appends), len(rows))
