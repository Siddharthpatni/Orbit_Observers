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
