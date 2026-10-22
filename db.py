import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    tg_id            INTEGER PRIMARY KEY,
    lead_id          TEXT,
    rev              INTEGER NOT NULL DEFAULT 0,
    synced           INTEGER NOT NULL DEFAULT 0,
    username         TEXT,
    first_name       TEXT,
    payload          TEXT,
    club             TEXT,
    phone            TEXT,
    age_confirmed    INTEGER NOT NULL DEFAULT 0,
    consent          INTEGER NOT NULL DEFAULT 0,
    consent_at       TEXT,
    consent_version  TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_deletes (lead_id TEXT PRIMARY KEY);
CREATE INDEX IF NOT EXISTS idx_leads_payload ON leads(payload);
CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at);
"""

COLUMNS = [
    "lead_id", "tg_id", "username", "first_name", "payload", "club", "phone",
    "age_confirmed", "consent", "consent_at", "consent_version", "created_at", "updated_at",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)
            cols = {r["name"] for r in c.execute("PRAGMA table_info(leads)")}
            for name, ddl in (("lead_id", "TEXT"), ("rev", "INTEGER NOT NULL DEFAULT 0"),
                              ("synced", "INTEGER NOT NULL DEFAULT 0")):
                if name not in cols:
                    c.execute(f"ALTER TABLE leads ADD COLUMN {name} {ddl}")
            c.execute("UPDATE leads SET lead_id=lower(hex(randomblob(16))) WHERE lead_id IS NULL")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # ---- sync implementations (run in a thread) ----
    def _save_lead(self, tg_id, username, first_name, payload, club, phone, consent_version, consent_at=None):
        now = _now()
        consent_at = consent_at or now
        with self._conn() as c:
            c.execute(
                """INSERT INTO leads (tg_id, lead_id, rev, synced, username, first_name, payload, club, phone,
                       age_confirmed, consent, consent_at, consent_version, created_at, updated_at)
                   VALUES (?,?,1,0,?,?,?,?,?,1,1,?,?,?,?)
                   ON CONFLICT(tg_id) DO UPDATE SET
                       lead_id=COALESCE(leads.lead_id, excluded.lead_id), rev=leads.rev+1, synced=0,
                       username=excluded.username, first_name=excluded.first_name,
                       club=COALESCE(excluded.club, leads.club), phone=excluded.phone,
                       age_confirmed=1, consent=1, consent_at=excluded.consent_at,
                       consent_version=excluded.consent_version, updated_at=excluded.updated_at""",
                (tg_id, str(uuid.uuid4()), username, first_name, payload, club, phone, consent_at, consent_version, now, now),
            )
            row = c.execute("SELECT * FROM leads WHERE tg_id=?", (tg_id,)).fetchone()
        return dict(row)

    def _set_club(self, tg_id, club):
        with self._conn() as c:
            n = c.execute("UPDATE leads SET club=?, updated_at=?, rev=rev+1, synced=0 WHERE tg_id=?", (club, _now(), tg_id)).rowcount
            row = c.execute("SELECT * FROM leads WHERE tg_id=?", (tg_id,)).fetchone() if n else None
        return dict(row) if row else None

    def _delete(self, tg_id):
        with self._conn() as c:
            row = c.execute("SELECT * FROM leads WHERE tg_id=?", (tg_id,)).fetchone()
            if not row:
                return None
            c.execute("INSERT OR IGNORE INTO pending_deletes(lead_id) VALUES (?)", (row["lead_id"],))
            c.execute("DELETE FROM leads WHERE tg_id=?", (tg_id,))
        return dict(row)

    def _unsynced(self, limit):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM leads WHERE synced=0 ORDER BY created_at LIMIT ?", (limit,))]

    def _mark_synced(self, pairs):
        with self._conn() as c:
            for tg_id, rev in pairs:  # only if nothing changed while the sync was running
                c.execute("UPDATE leads SET synced=1 WHERE tg_id=? AND rev=?", (tg_id, rev))

    def _pending_deletes(self):
        with self._conn() as c:
            return [r[0] for r in c.execute("SELECT lead_id FROM pending_deletes")]

    def _clear_pending(self, ids):
        with self._conn() as c:
            c.executemany("DELETE FROM pending_deletes WHERE lead_id=?", [(i,) for i in ids])

    def _stats(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            # created_at is stored as ISO-8601 with 'T'; compare against a cutoff in the same format
            cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
            day = c.execute("SELECT COUNT(*) FROM leads WHERE created_at >= ?", (cutoff,)).fetchone()[0]
            by_payload = c.execute(
                "SELECT COALESCE(NULLIF(payload,''),'(sin tag)') p, COUNT(*) n FROM leads GROUP BY p ORDER BY n DESC LIMIT 20"
            ).fetchall()
            by_club = c.execute(
                "SELECT COALESCE(club,'-') k, COUNT(*) n FROM leads GROUP BY k ORDER BY n DESC"
            ).fetchall()
        return {
            "total": total,
            "last_24h": day,
            "by_payload": [(r["p"], r["n"]) for r in by_payload],
            "by_club": [(r["k"], r["n"]) for r in by_club],
        }

    def _all(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM leads ORDER BY created_at")]

    # ---- async API ----
    async def save_lead(self, **kw):
        return await asyncio.to_thread(self._save_lead, **kw)

    async def set_club(self, tg_id: int, club: str):
        return await asyncio.to_thread(self._set_club, tg_id, club)

    async def delete(self, tg_id: int):
        """Returns the deleted lead (dict) or None. Its sheet row is removed by the sync worker."""
        return await asyncio.to_thread(self._delete, tg_id)

    async def unsynced(self, limit: int = 500) -> list[dict]:
        return await asyncio.to_thread(self._unsynced, limit)

    async def mark_synced(self, pairs) -> None:
        await asyncio.to_thread(self._mark_synced, list(pairs))

    async def pending_deletes(self) -> list[str]:
        return await asyncio.to_thread(self._pending_deletes)

    async def clear_pending(self, ids) -> None:
        await asyncio.to_thread(self._clear_pending, list(ids))

    async def stats(self) -> dict:
        return await asyncio.to_thread(self._stats)

    async def all_leads(self) -> list[dict]:
        return await asyncio.to_thread(self._all)
