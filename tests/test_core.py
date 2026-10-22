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
