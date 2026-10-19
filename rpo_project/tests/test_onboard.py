import copy
import random
import unittest

from onboard.recorder import ContactWindow, GroundArchive, OnboardRecorder, downlink


def win(**kw):
    d = dict(pass_id=0, start_s=100.0, duration_s=60.0, rate_bps=64_000, loss_prob=0.0, one_way_delay_s=0.01)
    d.update(kw)
    return ContactWindow(**d)


class OnboardTests(unittest.TestCase):
    def test_priority_order_on_downlink(self):
        r, g = OnboardRecorder("S", 10**6), GroundArchive()
        r.append("housekeeping", "info", "hk", 1.0, 100)
        r.append("event", "low", "ev", 2.0, 100)
        r.append("audit", "info", "au", 3.0, 100)
        downlink(r, win(), random.Random(0), g)
        by_kind = {x.kind: x.received_s for x in r.records}
        self.assertLess(by_kind["audit"], by_kind["event"])
        self.assertLess(by_kind["event"], by_kind["housekeeping"])

    def test_byte_budget_limits_pass_and_rest_waits(self):
        r, g = OnboardRecorder("S", 10**6), GroundArchive()
        for i in range(50):
            r.append("event", "low", f"e{i}", float(i), 1000)
        res = downlink(r, win(rate_bps=8000, duration_s=10), random.Random(0), g)   # ~8 kB budget at 80 % efficiency
        self.assertLess(res["delivered"], 50)
        self.assertLessEqual(res["used_b"], res["capacity_b"])
        self.assertTrue(any(x.status == "buffered" for x in r.records))

    def test_lost_packets_are_retried_next_pass(self):
        r, g = OnboardRecorder("S"), GroundArchive()
        r.append("audit", "info", "a", 1.0)
        downlink(r, win(loss_prob=1.0), random.Random(0), g)
        self.assertEqual(r.records[0].status, "retrying")
        downlink(r, win(pass_id=1, start_s=500.0), random.Random(0), g)
        self.assertEqual(r.records[0].status, "delivered")
        self.assertEqual(r.records[0].attempts, 2)

    def test_ground_outage_delivers_nothing(self):
        r, g = OnboardRecorder("S"), GroundArchive()
        r.append("audit", "info", "a", 1.0)
        res = downlink(r, win(ground_available=False), random.Random(0), g)
        self.assertEqual(res["sent"], 0)

    def test_full_buffer_drops_housekeeping_before_audit_and_leaves_gap(self):
        r, g = OnboardRecorder("S", 500), GroundArchive()
        r.append("audit", "info", "keep", 1.0, 200)
        r.append("housekeeping", "info", "hk1", 2.0, 200)
        r.append("housekeeping", "info", "hk2", 3.0, 200)
        self.assertEqual([x.status for x in r.records], ["buffered", "dropped", "buffered"])
        downlink(r, win(), random.Random(0), g)
        v = g.verify(3)
        self.assertTrue(v["ok"])
        self.assertEqual(v["missing_seq"], [2])

    def test_tampered_record_is_rejected_and_chain_detects_edit(self):
        r, g = OnboardRecorder("S"), GroundArchive()
        for i in range(3):
            r.append("audit", "info", f"a{i}", float(i))
        forged = copy.copy(r.records[1])
        forged.text = "forged"
        self.assertFalse(g.ingest(forged))
        for x in r.records:
            g.ingest(x)
        g.received[2] = copy.copy(g.received[2])
        g.received[2].prev_hash = "0" * 64                  # edited link
        self.assertEqual(g.verify(3)["tampered_seq"], [2])


if __name__ == "__main__":
    unittest.main()
