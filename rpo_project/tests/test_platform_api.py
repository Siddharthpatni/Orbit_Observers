import unittest

try:
    from fastapi.testclient import TestClient
    from platform_api.app import create_app
except ImportError:  # optional: pip install -r requirements-platform.txt
    TestClient = None
from platform_api.audit import AuditLog


@unittest.skipIf(TestClient is None, 'fastapi not installed')
class PlatformApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health(self):
        r = self.client.get("/health").json()
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["model_version"].startswith("Phase2-RPO-MC"))

    def test_feasibility_matches_stored_campaign(self):
        r = self.client.get("/feasibility", params={"tier": "C1", "tumble_deg_s": 3}).json()
        self.assertEqual(r["tier"], "C1_fiducials")
        self.assertTrue(r["within_tested_range"])
        c = r["cell"]
        self.assertEqual(c["n_pass"] / c["n_runs"], c["p_terminal_pass"])

    def test_out_of_range_is_flagged(self):
        r = self.client.get("/feasibility", params={"tier": "C2", "tumble_deg_s": 10}).json()
        self.assertFalse(r["within_tested_range"])
        self.assertTrue(any("above the tested range" in n for n in r["notes"]))

    def test_unknown_tier_404(self):
        self.assertEqual(self.client.get("/feasibility", params={"tier": "X", "tumble_deg_s": 1}).status_code, 404)

    def test_audit_chain_and_tamper_detection(self):
        log = AuditLog()
        for i in range(3):
            log.append("approval", "approver", f"event {i}", {"i": i})
        self.assertTrue(log.verify()["ok"])
        log._db.execute("UPDATE audit SET summary='forged' WHERE seq=2")
        self.assertEqual(log.verify(), {"ok": False, "first_bad_seq": 2})

    def test_audit_endpoints(self):
        self.client.post("/audit", json={"category": "approval", "actor": "a", "summary": "ok"})
        self.assertEqual(len(self.client.get("/audit").json()), 1)
        self.assertTrue(self.client.get("/audit/verify").json()["ok"])


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(TestClient is None, 'fastapi not installed')
class DomainRuleTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(create_app())
        self.c.put("/sync", json={
            "satellites": [{"id": "CS-1", "serviceTier": "C2_beacon", "estTumbleDegS": 3},
                           {"id": "CS-2", "serviceTier": "C2_beacon", "estTumbleDegS": 10}],
            "approvals": [{"id": "AP-1", "operation": "Close-proximity ops", "status": "pending"}],
            "missions": [{"id": "MS-1", "satId": "CS-1", "stage": 5, "gates": {"6": "AP-1"}, "events": []},
                         {"id": "MS-2", "satId": "CS-2", "stage": 5, "gates": {}, "events": []}],
        })

    def decide(self, role, notes="reviewed", decision="approved"):
        return self.c.post("/approvals/AP-1/decide", json={"decision": decision, "notes": notes, "role": role, "actor": "x"})

    def advance(self, mid, role="operator"):
        return self.c.post(f"/missions/{mid}/advance", json={"role": role, "actor": "x"})

    def test_only_approver_may_decide_and_notes_required(self):
        self.assertEqual(self.decide("operator").status_code, 403)
        self.assertEqual(self.decide("approver", notes=" ").status_code, 422)
        self.assertEqual(self.decide("approver").status_code, 200)
        self.assertEqual(self.decide("approver").status_code, 409)

    def test_gate_blocks_rendezvous_until_approved_then_ios_episode_runs(self):
        self.assertEqual(self.advance("MS-1").status_code, 200)        # planning -> rendezvous (feasibility recorded)
        m = self.c.get("/missions").json()[0]
        self.assertEqual(m["feasibility"]["tier"], "C2_beacon")
        self.assertEqual(self.advance("MS-1").status_code, 409)         # gate AP-1 still pending
        self.decide("approver")
        r = self.advance("MS-1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ios_episode"]["outcome"], "SERVICED_AND_RELEASED")
        self.assertEqual(r.json()["stage"], 7)

    def test_out_of_range_tumble_blocks_planning(self):
        r = self.advance("MS-2")
        self.assertEqual(r.status_code, 409)
        self.assertIn("tested range", r.json()["detail"])

    def test_operator_role_required_and_everything_audited(self):
        self.assertEqual(self.advance("MS-1", role="customer").status_code, 403)
        self.decide("approver")
        self.assertTrue(self.c.get("/audit/verify").json()["ok"])
        self.assertTrue(any("approved" in e["summary"] for e in self.c.get("/audit").json()))
