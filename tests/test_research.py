import unittest
from research.evaluate import evaluate


class BlindEvaluation(unittest.TestCase):
    def row(self, utc, truth, prediction):
        return dict(deployment="A", split="held-out", window_start_utc=utc,
                    target="UF310", noise="quiet", review=truth, prediction=prediction)

    def test_masking_and_denominators(self):
        rows = [self.row("2020-01-01T00:00:00Z","present","present"),
                self.row("2020-01-01T00:00:30Z","absent","present"),
                self.row("2020-01-01T00:01:00Z","unknown","absent")]
        result = evaluate(rows)[0]
        self.assertEqual((result["precision"],result["recall"],result["false_positive_rate"]),
                         (.5,1,1))
        self.assertEqual(result["excluded"],1)
        self.assertIsNone(evaluate(rows[2:])[0]["recall"])

    def test_leakage_rejected(self):
        a = self.row("2020-01-01T00:00:00Z","absent","absent")
        for b in (a, dict(a, split="development",window_start_utc="2020-01-01T00:15:00Z")):
            with self.assertRaises(ValueError):
                evaluate([a,b])
