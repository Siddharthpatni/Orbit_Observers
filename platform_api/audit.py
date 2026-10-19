"""Append-only, hash-chained audit log (SQLite). Tamper-evident, not tamper-proof."""
import hashlib
import json
import sqlite3
import threading
import time

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, category TEXT,"
            " actor TEXT, summary TEXT, detail TEXT, prev_hash TEXT, hash TEXT)"
        )
        self._db.commit()

    @staticmethod
    def _digest(prev: str, ts: float, category: str, actor: str, summary: str, detail: dict) -> str:
        body = json.dumps([prev, ts, category, actor, summary, detail], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()

    def append(self, category: str, actor: str, summary: str, detail: dict | None = None) -> dict:
        detail = detail or {}
        with self._lock:
            row = self._db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            ts = time.time()
            h = self._digest(prev, ts, category, actor, summary, detail)
            cur = self._db.execute(
                "INSERT INTO audit (ts, category, actor, summary, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?)",
                (ts, category, actor, summary, json.dumps(detail, sort_keys=True), prev, h),
            )
            self._db.commit()
            return {"seq": cur.lastrowid, "ts": ts, "category": category, "actor": actor,
                    "summary": summary, "detail": detail, "prev_hash": prev, "hash": h}

    def list(self, limit: int = 100) -> list[dict]:
        rows = self._db.execute(
            "SELECT seq, ts, category, actor, summary, detail, prev_hash, hash FROM audit ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
        keys = ("seq", "ts", "category", "actor", "summary", "detail", "prev_hash", "hash")
        out = [dict(zip(keys, r)) for r in rows]
        for r in out:
            r["detail"] = json.loads(r["detail"])
        return out

    def verify(self) -> dict:
        prev = GENESIS
        for seq, ts, cat, actor, summ, det, ph, h in self._db.execute(
            "SELECT seq, ts, category, actor, summary, detail, prev_hash, hash FROM audit ORDER BY seq"
        ):
            if ph != prev or h != self._digest(prev, ts, cat, actor, summ, json.loads(det)):
                return {"ok": False, "first_bad_seq": seq}
            prev = h
        return {"ok": True, "first_bad_seq": None}
