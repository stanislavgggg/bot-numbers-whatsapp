import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import Database  # noqa: E402
from phone import normalize_phone, pretty_phone  # noqa: E402


def test_phone_valid_variants():
    assert normalize_phone("612 345 678") == "+34612345678"
    assert normalize_phone("+34 612345678") == "+34612345678"
    assert normalize_phone("0034612345678") == "+34612345678"
    assert normalize_phone("34612345678") == "+34612345678"  # Telegram contact format
    assert normalize_phone("612-345-678") == "+34612345678"


def test_phone_invalid():
    assert normalize_phone("") is None
    assert normalize_phone("123") is None
    assert normalize_phone("abc") is None
    assert normalize_phone("000000000") is None


def test_pretty():
    assert pretty_phone("+34612345678") == "+34 612 34 56 78"


def test_db_roundtrip(tmp_path):
    db = Database(str(tmp_path / "t.db"))

    async def run():
        lead = await db.save_lead(tg_id=1, username="u", first_name="A", payload="A1",
                                  club="Barça", phone="+34612345678", consent_version="v1")
        assert lead["consent"] == 1 and lead["phone"] == "+34612345678"
        # same user again = update, not duplicate
        await db.save_lead(tg_id=1, username="u", first_name="A", payload="ignored",
                           club="Real Madrid", phone="+34699999999", consent_version="v1")
        await db.save_lead(tg_id=2, username=None, first_name="B", payload="",
                           club="Otro equipo", phone="+34611111111", consent_version="v1")
        s = await db.stats()
        assert s["total"] == 2
        assert dict(s["by_payload"])["A1"] == 1  # first-touch tag is kept
        assert len(await db.all_leads()) == 2
        gone = await db.delete(1)
        assert gone and gone["lead_id"]
        assert await db.delete(1) is None
        assert await db.pending_deletes() == [gone["lead_id"]]
        assert (await db.stats())["total"] == 1

    asyncio.run(run())


def test_phone_only_mobiles():
    # WhatsApp lives on mobile lines: landline (91x), toll-free (800) are rejected
    assert normalize_phone("912345678") is None
    assert normalize_phone("800123456") is None
    assert normalize_phone("711223344") == "+34711223344"   # 7xx mobiles are valid too
    assert normalize_phone("+44 7911 123456") == "+447911123456"
    assert normalize_phone("+370 612 34567") == "+37061234567"


def test_stats_last_24h_uses_real_cutoff(tmp_path):
    from datetime import datetime, timedelta, timezone
    db = Database(str(tmp_path / "s.db"))

    async def run():
        await db.save_lead(tg_id=1, username="u", first_name="A", payload="", club=None,
                           phone="+34612345678", consent_version="v")
        await db.save_lead(tg_id=2, username="u", first_name="B", payload="", club=None,
                           phone="+34611111111", consent_version="v")
        old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec="seconds")
        with db._conn() as c:
            c.execute("UPDATE leads SET created_at=? WHERE tg_id=1", (old,))
        s = await db.stats()
        assert s["total"] == 2 and s["last_24h"] == 1     # the 30-hour-old lead must not count

    asyncio.run(run())


def test_config_url_and_secret_file(tmp_path, monkeypatch):
    import config
    assert config._https("@MiCanal") == "https://t.me/MiCanal"
    assert config._https("t.me/MiCanal") == "https://t.me/MiCanal"
    assert config._https("example.com/privacidad") == "https://example.com/privacidad"
    assert config._https("https://x.y") == "https://x.y" and config._https("") == ""
    key = tmp_path / "sa.json"
    key.write_text('{"a": 1}\n')
    assert config._service_account("", str(key)) == '{"a": 1}'
    assert config._service_account('{"b": 2}', str(key)) == '{"b": 2}'   # the env JSON wins
    monkeypatch.setenv("BOT_TOKEN", "1:x")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key))
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    assert config.load_config().google_sa_json == '{"a": 1}'


def test_disclaimer_env(monkeypatch):
    import config
    monkeypatch.setenv("BOT_TOKEN", "1:x")
    monkeypatch.delenv("DISCLAIMER", raising=False)
    assert config.load_config().disclaimer == "short"
    monkeypatch.setenv("DISCLAIMER", "FULL")
    assert config.load_config().disclaimer == "full"
    monkeypatch.setenv("DISCLAIMER", "whatever")
    assert config.load_config().disclaimer == "short"


def test_proof_defaults_and_switch_off(monkeypatch):
    import config, texts
    monkeypatch.setenv("BOT_TOKEN", "1:x")
    for k in ("PROOF_LINE", "RESULTS_LINE", "BONUS_URL"):
        monkeypatch.delenv(k, raising=False)
    cfg = config.load_config()
    assert cfg.proof_line == texts.DEFAULT_PROOF_LINE and "+2.800" in cfg.proof_line
    assert "+572" in cfg.results_line and "no auditado" in cfg.results_line     # the number never travels without its caveat
    assert cfg.bonus_url == ""                                                    # the bonus is off until a link is given
    monkeypatch.setenv("RESULTS_LINE", "-")
    monkeypatch.setenv("PROOF_LINE", "Más de 3.000 aficionados")
    monkeypatch.setenv("BONUS_URL", "t.me/ApuestasGuruES/123")
    cfg = config.load_config()
    assert cfg.results_line == "" and cfg.proof_line == "Más de 3.000 aficionados"
    assert cfg.bonus_url == "https://t.me/ApuestasGuruES/123"
