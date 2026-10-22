import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config  # noqa: E402
from db import Database  # noqa: E402
from sheets import HEADERS, SheetSink, lead_to_row, split_payload  # noqa: E402


class FakeWS:
    """Minimal stand-in for gspread.Worksheet."""
    def __init__(self, headers):
        self.rows = [list(headers)]
        self.calls = 0

    def row_values(self, n): return list(self.rows[n - 1])
    def col_values(self, n): return [r[n - 1] if len(r) >= n else "" for r in self.rows]

    def append_rows(self, values, **kw):
        self.calls += 1
        self.rows.extend([list(v) for v in values])

    def batch_update(self, data, **kw):
        self.calls += 1
        for d in data:
            r = int(re.match(r"[A-Z]+(\d+):", d["range"]).group(1))
            self.rows[r - 1] = list(d["values"][0])

    def delete_rows(self, i, j=None):
        self.calls += 1
        del self.rows[i - 1]


CFG = Config(bot_token="1:x", brand_name="ACME Media", sheet_tz="Europe/Madrid")


def make_lead(**over):
    lead = {"lead_id": "L1", "created_at": "2026-10-22T11:42:49+00:00", "phone": "+34612345678",
            "club": None, "payload": "A1", "consent": 1, "consent_version": "es-tg-v2"}
    lead.update(over)
    return lead


def test_payload_split():
    assert split_payload("") == ("", "", "")
    assert split_payload("A1") == ("", "A1", "")
    assert split_payload("camp__A1") == ("camp", "A1", "")
    assert split_payload("camp__A1__kw") == ("camp", "A1", "kw")


def test_row_mapping():
    row = lead_to_row(make_lead(club="Barça"), CFG, "mybot")
    assert list(row) == HEADERS                         # exactly the sheet's 22 columns
    assert row["timestamp"] == "22/10/2026 13:42:49"    # UTC -> Europe/Madrid, sheet's dd/mm/yyyy format
    assert row["phone"] == "34612345678" and row["geo"] == "ES"
    assert row["club"] == row["favourite_team"] == "barca"
    assert row["whatsapp_consent"] is True and row["consent"] is True
    assert row["consent_text_version"] == "es-tg-v2"
    assert row["utm_source"] == "telegram" and row["utm_content"] == "A1" and row["brand"] == "ACME Media"
    assert row["landing_url"] == "https://t.me/mybot?start=A1" and row["referrer"] == "telegram"
    assert json.loads(row["answers_json"]) == {"flow": "telegram_bot", "club": "barca"}
    assert row["email"] == "" and row["fbclid"] == ""


def test_sync_append_update_delete_and_column_order():
    # sheet with a different column order and an extra column the bot knows nothing about
    headers = ["lead_id", "notes"] + [h for h in reversed(HEADERS) if h != "lead_id"]
    ws = FakeWS(headers)
    ws.rows.append(["OLD", "keep me"] + [""] * (len(headers) - 2))   # a row from the web quizzes
    sink = SheetSink(ws, CFG, "mybot")

    sink.sync([make_lead()], [])
    assert len(ws.rows) == 3
    new = dict(zip(headers, ws.rows[2]))
    assert new["lead_id"] == "L1" and new["phone"] == "34612345678" and new["club"] == ""
    assert new["notes"] == ""

    # same lead again with a club: same row is rewritten, no duplicate; other rows untouched
    sink.sync([make_lead(club="Real Madrid")], [])
    assert len(ws.rows) == 3
    assert dict(zip(headers, ws.rows[2]))["club"] == "real_madrid"
    assert ws.rows[1][:2] == ["OLD", "keep me"]

    # deletion removes only that lead's row
    sink.sync([], ["L1", "unknown-id"])
    assert len(ws.rows) == 2 and ws.rows[1][0] == "OLD"


def test_batch_uses_constant_api_calls():
    ws = FakeWS(HEADERS)
    sink = SheetSink(ws, CFG, "b")
    sink.sync([make_lead(lead_id=f"L{i}", phone="+3461234%04d" % i) for i in range(200)], [])
    assert len(ws.rows) == 201 and ws.calls == 1        # 200 leads, one write


def test_refuses_sheet_without_lead_id():
    import pytest
    with pytest.raises(RuntimeError):
        SheetSink(FakeWS(["timestamp", "phone"]), CFG)


def test_db_unsynced_cycle(tmp_path):
    db = Database(str(tmp_path / "s.db"))

    async def run():
        await db.save_lead(tg_id=1, username="u", first_name="A", payload="A1", club=None,
                           phone="+34612345678", consent_version="es-tg-v2")
        [lead] = await db.unsynced()
        assert lead["synced"] == 0 and lead["lead_id"]
        await db.set_club(1, "Barça")          # change arrives while the sync is "running"
        await db.mark_synced([(lead["tg_id"], lead["rev"])])
        assert len(await db.unsynced()) == 1   # stale rev -> still pending, will be re-synced
        [lead2] = await db.unsynced()
        await db.mark_synced([(lead2["tg_id"], lead2["rev"])])
        assert await db.unsynced() == []

    asyncio.run(run())


def test_sync_loop_pushes_updates_and_deletes(tmp_path):
    """The real background loop (as started in main): new lead, club update, /borrar all reach the sheet once."""
    import bot as botmod

    async def run():
        cfg = Config(bot_token="1:x", sync_interval=0.05, sheet_tz="Europe/Madrid")
        db = Database(str(tmp_path / "l.db"))
        ws = FakeWS(HEADERS)
        task = botmod.spawn(botmod.sync_loop(cfg, db, SheetSink(ws, cfg, "mybot")))
        await db.save_lead(tg_id=1, username="u", first_name="A", payload="A1", club=None,
                           phone="+34612345678", consent_version="es-tg-v3")
        await asyncio.sleep(0.3)
        assert len(ws.rows) == 2 and ws.rows[1][HEADERS.index("phone")] == "34612345678"
        await db.set_club(1, "Barça")
        await asyncio.sleep(0.3)
        assert len(ws.rows) == 2 and ws.rows[1][HEADERS.index("club")] == "barca"   # same row, no duplicate
        await db.delete(1)
        await asyncio.sleep(0.3)
        assert len(ws.rows) == 1                                                     # row removed
        task.cancel()

    asyncio.run(run())
