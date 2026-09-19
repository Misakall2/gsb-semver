import unittest

from semverlib import Version, InvalidVersion


class TestParsing(unittest.TestCase):
    def test_basic(self):
        v = Version("1.2.3")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))
        self.assertFalse(v.is_prerelease)

    def test_leading_v_stripped(self):
        self.assertEqual(Version("v1.2.0-alpha.1+build"), Version("1.2.0-alpha.1"))
        v = Version("v1.2.0-alpha.1+build")
        self.assertEqual(v.build, "build")
        self.assertTrue(v.is_prerelease)

    def test_invalid_raises(self):
        for bad in ["1.2", "1", "1.2.3.4", "01.2.3", "1.2.x", "", "v",
                    "1.2.3-", "1.2.3-alpha..1", "1.2.3+", "1.2.3-01"]:
            with self.assertRaises(InvalidVersion, msg=bad):
                Version(bad)

    def test_str_roundtrip(self):
        for s in ["1.2.3", "1.0.0-alpha.1", "2.0.0+build.5", "0.0.0"]:
            self.assertEqual(str(Version(s)), s)


class TestComparison(unittest.TestCase):
    def test_release_order(self):
        self.assertLess(Version("1.0.0"), Version("1.0.1"))
        self.assertLess(Version("1.9.9"), Version("1.10.0"))
        self.assertLess(Version("1.2.3"), Version("2.0.0"))

    def test_prerelease_chain(self):
        ordered = [
            "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta",
            "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
            "1.0.0-rc.1", "1.0.0",
        ]
        versions = [Version(s) for s in ordered]
        for a, b in zip(versions, versions[1:]):
            self.assertLess(a, b)
        self.assertEqual(versions, sorted(reversed(versions)))

    def test_numeric_vs_alpha_identifiers(self):
        # Numeric identifiers compare numerically and sort before alphanumeric.
        self.assertLess(Version("1.0.0-2"), Version("1.0.0-11"))
        self.assertLess(Version("1.0.0-1"), Version("1.0.0-alpha"))

    def test_build_metadata_ignored(self):
        self.assertEqual(Version("1.0.0+build1"), Version("1.0.0+build2"))
        self.assertFalse(Version("1.0.0+aaa") < Version("1.0.0+bbb"))
        self.assertFalse(Version("1.0.0+aaa") > Version("1.0.0+bbb"))
        self.assertEqual(hash(Version("1.0.0+x")), hash(Version("1.0.0+y")))

    def test_prerelease_smaller_than_release(self):
        self.assertLess(Version("1.0.0-rc.99"), Version("1.0.0"))


if __name__ == "__main__":
    unittest.main()
