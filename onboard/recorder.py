"""On-board recorder and pass-based downlink (stdlib only).

What it does, in the order it happens on board:
  1. ``OnboardRecorder.append`` stores logs and audit entries in a bounded buffer. Every record carries a sequence number
     and a SHA-256 hash that includes the previous record's hash, so a missing or altered record is detectable on the ground.
  2. During a contact window, ``downlink`` sends unacknowledged records by priority (audit > critical event > event >
     housekeeping) within the byte budget of the pass, retrying lost ones in later passes until the ground acknowledges.
  3. ``GroundArchive.ingest`` re-computes each hash; ``verify`` reports gaps (records dropped on board) and tampering.
When the buffer is full the lowest-priority oldest record is dropped first; audit entries are dropped last, and every drop
leaves a visible sequence gap rather than silent loss.

Link rates, loss and delays are assumptions for a study, not measured values. The hash chain is tamper-evident, not a signature:
flight use would add an authenticated signature (see docs/SCOPE_ARCHITECTURE.md section 5).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import hashlib
import random

GENESIS = "0" * 64
PRIORITY = {"audit": 0, "critical": 1, "event": 2, "housekeeping": 3}
LINK_EFFICIENCY = 0.8     # framing, protocol overhead


def record_hash(prev: str, seq: int, kind: str, severity: str, text: str, created_s: float) -> str:
    return hashlib.sha256(f"{prev}|{seq}|{kind}|{severity}|{text}|{created_s:.3f}".encode()).hexdigest()


@dataclass
class Record:
    seq: int
    kind: str
    severity: str
    text: str
    created_s: float
    size_b: int
    prev_hash: str
    hash: str
    attempts: int = 0
    first_sent_s: Optional[float] = None
    last_sent_s: Optional[float] = None
    received_s: Optional[float] = None
    pass_id: Optional[int] = None
    dropped_s: Optional[float] = None

    @property
    def status(self) -> str:
        if self.received_s is not None:
            return "delivered"
        if self.dropped_s is not None:
            return "dropped"
        return "retrying" if self.attempts else "buffered"


@dataclass(frozen=True)
class ContactWindow:
    pass_id: int
    start_s: float
    duration_s: float
    rate_bps: float
    loss_prob: float
    one_way_delay_s: float
    ground_available: bool = True


class OnboardRecorder:
    def __init__(self, sat_id: str, capacity_bytes: int = 65536):
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be positive")
        self.sat_id, self.capacity = sat_id, capacity_bytes
        self.records: List[Record] = []          # every record ever created (for reporting); live buffer is the undelivered, undropped subset
        self._seq, self._last_hash = 0, GENESIS

    def _live(self) -> List[Record]:
        return [r for r in self.records if r.received_s is None and r.dropped_s is None]

    def append(self, kind: str, severity: str, text: str, t_s: float, size_b: Optional[int] = None) -> Record:
        if kind not in PRIORITY:
            raise ValueError(f"kind must be one of {sorted(PRIORITY)}")
        self._seq += 1
        size = size_b if size_b is not None else 64 + len(text) + 32
        h = record_hash(self._last_hash, self._seq, kind, severity, text, t_s)
        rec = Record(self._seq, kind, severity, text, t_s, size, self._last_hash, h)
        self._last_hash = h
        self.records.append(rec)
        self._enforce_capacity(t_s)
        return rec

    def _enforce_capacity(self, t_s: float) -> None:
        live = self._live()
        used = sum(r.size_b for r in live)
        # drop lowest priority first, oldest first; never drop the record just written unless it is the only candidate
        order = sorted(live[:-1] or live, key=lambda r: (-PRIORITY[r.kind], r.seq))
        for r in order:
            if used <= self.capacity:
                break
            r.dropped_s = t_s
            used -= r.size_b

    def pending(self) -> List[Record]:
        return sorted(self._live(), key=lambda r: (PRIORITY[r.kind], r.seq))


class GroundArchive:
    def __init__(self):
        self.received: Dict[int, Record] = {}

    def ingest(self, rec: Record) -> bool:
        ok = record_hash(rec.prev_hash, rec.seq, rec.kind, rec.severity, rec.text, rec.created_s) == rec.hash
        if ok:
            self.received[rec.seq] = rec
        return ok

    def verify(self, last_seq: int) -> Dict[str, object]:
        """Chain check over what arrived: tampering (link mismatch) is a failure; missing sequence numbers are reported as gaps."""
        bad, gaps = [], []
        for seq in range(1, last_seq + 1):
            r = self.received.get(seq)
            if r is None:
                gaps.append(seq)
            elif seq - 1 in self.received and r.prev_hash != self.received[seq - 1].hash:
                bad.append(seq)
        return {"ok": not bad, "tampered_seq": bad, "missing_seq": gaps}


def downlink(rec: OnboardRecorder, win: ContactWindow, rng: random.Random, ground: GroundArchive) -> Dict[str, object]:
    """Run one pass. Returns bytes capacity/used and counts; mutates the records' send/receive timestamps."""
    capacity = win.rate_bps / 8.0 * win.duration_s * LINK_EFFICIENCY
    used, t, sent, delivered, lost = 0.0, 0.0, 0, 0, 0
    if win.ground_available:
        for r in rec.pending():
            if r.created_s > win.start_s:
                continue
            dur = r.size_b * 8.0 / (win.rate_bps * LINK_EFFICIENCY)
            if t + dur > win.duration_s:
                break
            t += dur
            used += r.size_b
            sent += 1
            r.attempts += 1
            r.last_sent_s = win.start_s + t
            r.first_sent_s = r.first_sent_s if r.first_sent_s is not None else r.last_sent_s
            r.pass_id = win.pass_id
            if rng.random() < win.loss_prob:
                lost += 1
                continue
            r.received_s = win.start_s + t + win.one_way_delay_s
            ground.ingest(r)
            delivered += 1
    return {"pass_id": win.pass_id, "start_s": win.start_s, "duration_s": win.duration_s, "rate_bps": win.rate_bps,
            "capacity_b": round(capacity), "used_b": round(used), "sent": sent, "delivered": delivered, "lost": lost,
            "ground_available": win.ground_available}
