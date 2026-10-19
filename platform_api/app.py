"""FastAPI service: read-only feasibility + hash-chained audit. Run: uvicorn platform_api.app:app --reload"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audit import AuditLog
from .feasibility import FeasibilityTable


class AuditIn(BaseModel):
    category: str
    actor: str
    summary: str
    detail: dict = {}


def create_app(audit_path: str = ":memory:") -> FastAPI:
    app = FastAPI(title="Serviceable-Client Platform API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["*"])
    table = FeasibilityTable()
    audit = AuditLog(audit_path)

    @app.get("/health")
    def health():
        return {"status": "ok", "model_version": table.data["model_version"], "config_hash": table.data["config_hash"]}

    @app.get("/feasibility/tiers")
    def tiers():
        return {t: table.grid(t) for t in table.tiers()}

    @app.get("/feasibility")
    def feasibility(tier: str, tumble_deg_s: float):
        try:
            res = table.query(tier, tumble_deg_s)
        except KeyError as e:
            raise HTTPException(404, str(e.args[0]))
        audit.append("system", "feasibility-service", f"feasibility {res['tier']} @ {tumble_deg_s} deg/s",
                     {"config_hash": res["provenance"]["config_hash"], "within_tested_range": res["within_tested_range"]})
        return res

    @app.post("/audit")
    def audit_add(ev: AuditIn):
        return audit.append(ev.category, ev.actor, ev.summary, ev.detail)

    @app.get("/audit")
    def audit_list(limit: int = 100):
        return audit.list(limit)

    @app.get("/audit/verify")
    def audit_verify():
        return audit.verify()

    return app


app = create_app()
