import unittest

from semverlib import Range, Version, InvalidRange, InvalidVersion


class TestCaret(unittest.TestCase):
    def test_caret_basic(self):
        r = Range("^1.2.3")
        self.assertTrue(r.match("1.2.3"))
        self.assertTrue(r.match("1.9.9"))
        self.assertFalse(r.match("1.2.2"))
        self.assertFalse(r.match("2.0.0"))

    def test_caret_zero_major(self):
        r = Range("^0.2.3")
        self.assertTrue(r.match("0.2.9"))
        self.assertFalse(r.match("0.3.0"))
        r = Range("^0.0.3")
        self.assertTrue(r.match("0.0.3"))
        self.assertFalse(r.match("0.0.4"))

    def test_caret_boundary_excluded(self):
        self.assertFalse(Range("^1.2.3").match("2.0.0-alpha"))


class TestTilde(unittest.TestCase):
    def test_tilde_basic(self):
        r = Range("~1.2.3")
        self.assertTrue(r.match("1.2.3"))
        self.assertTrue(r.match("1.2.99"))
        self.assertFalse(r.match("1.3.0"))
        self.assertFalse(r.match("1.2.2"))

    def test_tilde_partial(self):
        r = Range("~1.2")
        self.assertTrue(r.match("1.2.0"))
        self.assertFalse(r.match("1.3.0"))
        r = Range("~1")
        self.assertTrue(r.match("1.99.0"))
        self.assertFalse(r.match("2.0.0"))


class TestComparators(unittest.TestCase):
    def test_anded_comparators(self):
        r = Range(">=1.0.0 <2")
        self.assertTrue(r.match("1.0.0"))
        self.assertTrue(r.match("1.5.0"))
        self.assertFalse(r.match("0.9.9"))
        self.assertFalse(r.match("2.0.0"))

    def test_exact_and_partial(self):
        self.assertTrue(Range("1.2.3").match("1.2.3"))
        self.assertFalse(Range("1.2.3").match("1.2.4"))
        self.assertTrue(Range("1.2").match("1.2.7"))
        self.assertFalse(Range("1.2").match("1.3.0"))

    def test_v_prefix_in_range(self):
        self.assertTrue(Range(">=v1.0.0 <v2.0.0").match("v1.5.0"))
        self.assertTrue(Range("^v1.2.3").match("1.5.0"))

    def test_prerelease_in_range(self):
        r = Range(">=1.0.0-alpha <1.0.0")
        self.assertTrue(r.match("1.0.0-beta.2"))
        self.assertFalse(r.match("1.0.0"))
        self.assertFalse(r.match("0.9.0"))


class TestUnion(unittest.TestCase):
    def test_or_short_circuit(self):
        r = Range("<1.0.0 || >=2.0.0")
        self.assertTrue(r.match("0.5.0"))
        self.assertTrue(r.match("2.5.0"))
        self.assertFalse(r.match("1.5.0"))

    def test_or_with_caret_and_tilde(self):
        r = Range("^1.0.0 || ~2.3.0")
        self.assertTrue(r.match("1.7.0"))
        self.assertTrue(r.match("2.3.9"))
        self.assertFalse(r.match("2.4.0"))
        self.assertFalse(r.match("3.0.0"))

    def test_contains_and_version_objects(self):
        r = Range("^1.2.3")
        self.assertIn(Version("1.4.0"), r)
        self.assertNotIn(Version("2.0.0"), r)


class TestInvalid(unittest.TestCase):
    def test_invalid_range_raises(self):
        for bad in ["", "   ", ">=", "^", "~", "1.2.x", "hello", ">=1.0.0 <"]:
            with self.assertRaises((InvalidRange, InvalidVersion), msg=bad):
                Range(bad)

    def test_invalid_version_in_match_raises(self):
        with self.assertRaises(InvalidVersion):
            Range("^1.0.0").match("not-a-version")


if __name__ == "__main__":
    unittest.main()
