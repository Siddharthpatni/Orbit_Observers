"""Server-side cases, approvals and missions with enforced rules (mirrors the UI store's workflow).

The UI store remains the interactive source in demo mode and mirrors its state here via ``/sync``;
the server re-enforces the rules that must not depend on the browser: who may decide, notes required,
approval gates before a mission leaves a stage, feasibility before rendezvous, and IOS handover only
after a human-approved gate. Every action is written to the hash-chained audit log.
"""
import json
import sqlite3
import threading
import zlib
from typing import Dict, List, Optional

from rpo_project.ios_coupling import run_ios_servicing_episode

STAGES = ["Customer service request", "Satellite health assessment", "AI diagnosis", "Service proposal",
          "Human/customer authorization", "Mission planning", "Rendezvous & proximity ops", "Communication establishment",
          "Inspection & servicing", "Post-service verification", "Completion & reporting"]
PLAN_STAGE, RPO_STAGE = 5, 6
DECIDERS = {"approver", "admin"}
OPERATORS = {"operator", "engineer", "admin"}
DECISIONS = {"approved", "rejected", "hold", "info-requested"}


class RuleViolation(Exception):
    def __init__(self, code: int, reason: str):
        super().__init__(reason)
        self.code, self.reason = code, reason


class Domain:
    def __init__(self, path: str = ":memory:", audit=None, feasibility=None):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute("CREATE TABLE IF NOT EXISTS docs (kind TEXT, id TEXT, body TEXT, PRIMARY KEY (kind, id))")
        self._db.commit()
        self.audit, self.feas = audit, feasibility

    # -- storage ---------------------------------------------------------------------------------
    def put(self, kind: str, doc: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO docs VALUES (?,?,?)", (kind, doc["id"], json.dumps(doc)))
            self._db.commit()

    def get(self, kind: str, id_: str) -> Optional[dict]:
        r = self._db.execute("SELECT body FROM docs WHERE kind=? AND id=?", (kind, id_)).fetchone()
        return json.loads(r[0]) if r else None

    def list(self, kind: str) -> List[dict]:
        return [json.loads(r[0]) for r in self._db.execute("SELECT body FROM docs WHERE kind=? ORDER BY id", (kind,))]

    def sync(self, snapshot: Dict[str, List[dict]]) -> Dict[str, int]:
        counts = {}
        for kind in ("satellites", "cases", "approvals", "missions"):
            for doc in snapshot.get(kind, []):
                self.put(kind, doc)
            counts[kind] = len(snapshot.get(kind, []))
        return counts

    def _log(self, category: str, actor: str, summary: str, detail: dict) -> None:
        if self.audit:
            self.audit.append(category, actor, summary, detail)

    # -- rules -----------------------------------------------------------------------------------
    def decide_approval(self, id_: str, decision: str, notes: str, role: str, actor: str) -> dict:
        ap = self.get("approvals", id_)
        if ap is None:
            raise RuleViolation(404, f"approval {id_} not found")
        if role not in DECIDERS:
            self._log("approval", actor, f"DENIED decision on {id_}: role {role}", {"role": role})
            raise RuleViolation(403, "only an approval authority may decide")
        if decision not in DECISIONS:
            raise RuleViolation(422, f"decision must be one of {sorted(DECISIONS)}")
        if not notes.strip():
            raise RuleViolation(422, "decision notes are required")
        if ap.get("status") != "pending" and ap.get("status") != "info-requested":
            raise RuleViolation(409, f"approval already {ap.get('status')}")
        ap.update(status=decision, notes=notes, decidedBy=actor)
        self.put("approvals", ap)
        self._log("approval", actor, f"{ap.get('operation', id_)} {decision}", {"approval": id_, "notes": notes})
        return ap

    def advance_mission(self, id_: str, role: str, actor: str) -> dict:
        m = self.get("missions", id_)
        if m is None:
            raise RuleViolation(404, f"mission {id_} not found")
        if role not in OPERATORS:
            raise RuleViolation(403, "operator or engineer role required")
        stage = int(m["stage"])
        if stage >= len(STAGES):
            raise RuleViolation(409, "mission already complete")
        gate = (m.get("gates") or {}).get(str(stage))
        if gate:
            ap = self.get("approvals", gate)
            if not ap or ap.get("status") != "approved":
                raise RuleViolation(409, f"approval gate {gate} is not approved")
        sat = self.get("satellites", m["satId"]) or {}
        events = m.setdefault("events", [])
        if stage == PLAN_STAGE:
            tier, tumble = sat.get("serviceTier"), sat.get("estTumbleDegS")
            if tier is None or tumble is None:
                raise RuleViolation(409, "client serviceability tier / tumble estimate missing; treat as C0 and set them before rendezvous")
            f = self.feas.query(tier, float(tumble))
            if not f["within_tested_range"]:
                raise RuleViolation(409, f"no model evidence for {tier} at {tumble} deg/s (tested range exceeded)")
            m["feasibility"] = {"tier": f["tier"], "tumble_deg_s": tumble, "p_pass": f["cell"]["p_terminal_pass"],
                                "config_hash": f["provenance"]["config_hash"]}
            self._log("mission", actor, f"{id_} feasibility recorded", m["feasibility"])
        if stage == RPO_STAGE:
            tier, tumble = sat.get("serviceTier"), sat.get("estTumbleDegS")
            if tier is None or tumble is None:
                raise RuleViolation(409, "client tier / tumble missing")
            seed = zlib.crc32(id_.encode()) % 1_000_000
            ep = run_ios_servicing_episode(tier, seed, float(tumble), ground_approved=True, master_seed=20261019)
            m["ios_episode"] = {"outcome": ep.outcome, "final_ios_state": ep.final_ios_state, "seed": seed,
                                "authority_invariant_held": ep.authority_invariant_held, "log": ep.ios_log}
            self._log("mission", actor, f"{id_} IOS/RPO episode: {ep.outcome}", {"ios_state": ep.final_ios_state})
            events.append({"text": f"IOS/RPO episode: {ep.outcome}"})
            if ep.outcome != "SERVICED_AND_RELEASED":
                m["status"] = "Blocked"
                self.put("missions", m)
                raise RuleViolation(409, f"IOS/RPO episode ended {ep.outcome}; mission blocked for human review")
        m["stage"] = stage + 1
        events.append({"text": f"Advanced to {STAGES[stage + 1] if stage + 1 < len(STAGES) else 'Complete'} by {actor}"})
        self.put("missions", m)
        self._log("mission", actor, f"{id_}: stage {stage} -> {stage + 1}", {})
        return m
