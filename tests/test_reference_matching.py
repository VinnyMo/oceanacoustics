import unittest

import numpy as np

from classification.references import compare, profile


class ReferenceComparison(unittest.TestCase):
    def test_invalid_and_silent(self):
        with self.assertRaises(ValueError):
            profile(np.array([1]))
        with self.assertRaises(ValueError):
            profile(np.full(2000,np.nan))
        self.assertEqual(compare(np.zeros(4000))["scores"], {"UF310":None, "UF440":None})

    def test_gain_invariant(self):
        rng = np.random.default_rng(10)
        x = rng.normal(size=12000)/8
        result = compare(x)["scores"]
        self.assertEqual(set(result), {"UF310","UF440"})
        self.assertTrue(all(-1 <= value <= 1 for value in result.values()))
        self.assertEqual(result, compare(x/7)["scores"])
