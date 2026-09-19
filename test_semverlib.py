import unittest

from semverlib import (
    InvalidRange,
    InvalidVersion,
    Range,
    Version,
    compare,
    parse,
)


class TestParse(unittest.TestCase):
    def test_basic(self):
        v = parse("1.2.3")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))
        self.assertIsNone(v.prerelease)
        self.assertIsNone(v.build)

    def test_leading_v_stripped(self):
        self.assertEqual(parse("v1.2.0"), parse("1.2.0"))
        self.assertEqual(parse("v1.2.0-alpha.1+build"), parse("1.2.0-alpha.1+build"))

    def test_prerelease_and_build(self):
        v = parse("1.2.0-alpha.1+build.5")
        self.assertEqual(v.prerelease, ("alpha", "1"))
        self.assertEqual(v.build, "build.5")
        self.assertEqual(str(v), "1.2.0-alpha.1+build.5")

    def test_invalid_strings_raise(self):
        for bad in ["", "1.2", "1.2.3.4", "01.2.3", "1.2.x", "1.2.3-",
                    "1.2.3-alpha..1", "1.2.3+", "v", "latest", None, 123]:
            with self.assertRaises(InvalidVersion, msg=repr(bad)):
                parse(bad)


class TestCompare(unittest.TestCase):
    def test_numeric_order(self):
        self.assertLess(parse("1.2.3"), parse("1.10.0"))
        self.assertLess(parse("2.0.0"), parse("10.0.0"))

    def test_prerelease_chain_from_spec(self):
        chain = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        versions = [parse(s) for s in chain]
        for a, b in zip(versions, versions[1:]):
            self.assertLess(a, b, f"{a} should be < {b}")
        self.assertEqual(sorted(reversed(versions)), versions)

    def test_prerelease_less_than_release(self):
        self.assertLess(parse("1.0.0-rc.99"), parse("1.0.0"))
        self.assertGreater(parse("1.0.0"), parse("1.0.0-alpha"))

    def test_numeric_identifiers_below_alpha(self):
        self.assertLess(parse("1.0.0-1"), parse("1.0.0-alpha"))
        self.assertLess(parse("1.0.0-alpha.2"), parse("1.0.0-alpha.10"))

    def test_build_metadata_ignored_in_ordering(self):
        self.assertEqual(parse("1.2.3+build.1"), parse("1.2.3+build.2"))
        self.assertEqual(parse("1.2.3+build"), parse("1.2.3"))
        self.assertFalse(parse("1.2.3+a") < parse("1.2.3+b"))
        self.assertEqual(compare("1.2.3+aaa", "1.2.3+zzz"), 0)
        # but build is preserved in the value
        self.assertEqual(parse("1.2.3+aaa").build, "aaa")
        self.assertNotEqual(str(parse("1.2.3+a")), str(parse("1.2.3+b")))

    def test_equality_and_hash(self):
        self.assertEqual(parse("v1.0.0"), Version(1, 0, 0))
        self.assertEqual(hash(parse("1.0.0+a")), hash(parse("1.0.0+b")))
        self.assertNotEqual(parse("1.0.0-alpha"), parse("1.0.0"))


class TestRange(unittest.TestCase):
    def test_caret(self):
        r = Range("^1.2.3")
        self.assertTrue(r.matches("1.2.3"))
        self.assertTrue(r.matches("1.9.9"))
        self.assertFalse(r.matches("2.0.0"))
        self.assertFalse(r.matches("1.2.2"))

    def test_caret_zero_major(self):
        self.assertTrue(Range("^0.2.3").matches("0.2.9"))
        self.assertFalse(Range("^0.2.3").matches("0.3.0"))
        self.assertTrue(Range("^0.0.3").matches("0.0.3"))
        self.assertFalse(Range("^0.0.3").matches("0.0.4"))

    def test_tilde(self):
        r = Range("~1.2.3")
        self.assertTrue(r.matches("1.2.3"))
        self.assertTrue(r.matches("1.2.99"))
        self.assertFalse(r.matches("1.3.0"))
        self.assertFalse(r.matches("1.2.2"))

    def test_compound_and(self):
        r = Range(">=1.0.0 <2")
        self.assertTrue(r.matches("1.0.0"))
        self.assertTrue(r.matches("1.99.0"))
        self.assertFalse(r.matches("2.0.0"))
        self.assertFalse(r.matches("0.9.9"))

    def test_boundary_inclusivity(self):
        self.assertTrue(Range(">=1.0.0").matches("1.0.0"))
        self.assertTrue(Range("<=1.0.0").matches("1.0.0"))
        self.assertFalse(Range(">1.0.0").matches("1.0.0"))
        self.assertFalse(Range("<1.0.0").matches("1.0.0"))
        self.assertTrue(Range("=1.0.0").matches("1.0.0"))
        self.assertTrue(Range("1.0.0").matches("v1.0.0"))
        self.assertFalse(Range("!=1.0.0").matches("1.0.0"))

    def test_or_union(self):
        r = Range("<1.0.0 || >=2.0.0")
        self.assertTrue(r.matches("0.5.0"))
        self.assertTrue(r.matches("2.0.0"))
        self.assertFalse(r.matches("1.5.0"))

    def test_or_short_circuit_first_clause_wins(self):
        # First clause already matches; a broken-looking second clause would
        # fail at parse time, so verify evaluation order with a valid range.
        r = Range("^1.0.0 || ^2.0.0")
        self.assertTrue(r.matches("1.5.0"))
        self.assertTrue(r.matches("2.5.0"))
        self.assertFalse(r.matches("3.0.0"))
        # matches() returns as soon as one clause is true
        calls = []

        class Spy:
            def __init__(self, result):
                self.result = result

            def matches(self, v):
                calls.append(self.result)
                return self.result

        r2 = Range.__new__(Range)
        r2.clauses = [Spy(True), Spy(True)]
        self.assertTrue(r2.matches(parse("9.9.9")))
        self.assertEqual(calls, [True])  # second clause never evaluated

    def test_prerelease_in_range(self):
        self.assertTrue(Range(">=1.0.0-alpha").matches("1.0.0-beta"))
        self.assertFalse(Range(">1.0.0").matches("1.0.0-alpha"))
        self.assertTrue(Range("<1.0.0").matches("1.0.0-alpha"))

    def test_build_metadata_in_range(self):
        self.assertTrue(Range("=1.2.3").matches("1.2.3+build.7"))
        self.assertTrue(Range("=1.2.3+anything").matches("1.2.3"))

    def test_contains_operator(self):
        self.assertIn(parse("1.5.0"), Range("^1.0.0"))
        self.assertNotIn(parse("2.0.0"), Range("^1.0.0"))

    def test_invalid_range_raises(self):
        for bad in ["", "   ", ">=", "^", "~", ">=1.2.3 ||", "|| >=1.0.0",
                    ">=abc", "^1.x", None]:
            with self.assertRaises((InvalidRange, InvalidVersion), msg=repr(bad)):
                Range(bad)

    def test_partial_versions_in_range(self):
        self.assertTrue(Range(">=1.0.0 <2").matches("1.99.0"))
        self.assertFalse(Range(">=1.0.0 <2").matches("2.0.0"))
        self.assertTrue(Range("~1.2").matches("1.2.0"))
        self.assertFalse(Range("~1.2").matches("1.3.0"))
        self.assertTrue(Range("^1").matches("1.9.9"))
        self.assertFalse(Range("^1").matches("2.0.0"))


if __name__ == "__main__":
    unittest.main()
