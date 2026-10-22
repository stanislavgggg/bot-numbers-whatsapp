import os
from dataclasses import dataclass, field


def _ids(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()}


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int] = field(default_factory=set)
    privacy_url: str = ""          # link to the privacy policy shown in the disclaimer
    brand_name: str = ""           # who sends the WhatsApp messages (default: Apuestas Guru)
    channel_url: str = ""          # optional: public channel button shown after signup
    frequency_line: str = ""       # optional trust line, e.g. "Máximo 3 mensajes por semana" (must match reality)
    proof_line: str = ""           # optional social proof, e.g. "Más de 2.000 aficionados ya lo reciben" (only if true)
    webhook_url: str = ""          # optional: every new lead is POSTed here (Make.com, Zapier, Sheets script)
    webhook_secret: str = ""       # optional: sent as X-Webhook-Secret header
    db_path: str = "data/leads.db"
    default_region: str = "ES"     # used to parse numbers typed without a country code
    # --- Google Sheets (optional; leave gsheet_id empty to keep leads in SQLite only) ---
    gsheet_id: str = ""
    gsheet_gid: str = ""           # worksheet (tab) id from the URL: ...#gid=1091185446
    google_sa_json: str = ""       # full service-account key JSON (as a string)
    sheet_tz: str = "Europe/Madrid"
    quiz_id: str = "es_whatsapp_tgbot"
    utm_source: str = "telegram"
    utm_medium: str = ""
    sync_interval: float = 10.0    # seconds between batched syncs to the sheet


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    return Config(
        bot_token=token,
        admin_ids=_ids(os.environ.get("ADMIN_IDS", "")),
        privacy_url=os.environ.get("PRIVACY_URL", "").strip(),
        brand_name=os.environ.get("BRAND_NAME", "").strip(),
        channel_url=os.environ.get("CHANNEL_URL", "").strip(),
        frequency_line=os.environ.get("FREQUENCY_LINE", "").strip(),
        proof_line=os.environ.get("PROOF_LINE", "").strip(),
        webhook_url=os.environ.get("WEBHOOK_URL", "").strip(),
        webhook_secret=os.environ.get("WEBHOOK_SECRET", "").strip(),
        db_path=os.environ.get("DB_PATH", "data/leads.db").strip(),
        default_region=os.environ.get("DEFAULT_REGION", "ES").strip().upper(),
        gsheet_id=os.environ.get("GSHEET_ID", "").strip(),
        gsheet_gid=os.environ.get("GSHEET_GID", "").strip(),
        google_sa_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip(),
        sheet_tz=os.environ.get("SHEET_TZ", "Europe/Madrid").strip(),
        quiz_id=os.environ.get("QUIZ_ID", "es_whatsapp_tgbot").strip(),
        utm_source=os.environ.get("UTM_SOURCE", "telegram").strip(),
        utm_medium=os.environ.get("UTM_MEDIUM", "").strip(),
        sync_interval=float(os.environ.get("SYNC_INTERVAL", "10")),
    )
