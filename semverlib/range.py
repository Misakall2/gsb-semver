"""SemVer range matching: comparators, ^, ~, and || unions."""

import re

from .version import Version


class InvalidRange(ValueError):
    """Raised when a range expression cannot be parsed."""


_PARTIAL_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:-([0-9a-zA-Z.-]+))?(?:\+[0-9a-zA-Z.-]+)?$"
)

_OP_RE = re.compile(r"^(<=|>=|<|>|=)?\s*(.*)$")


def _parse_partial(text):
    """Parse '1', '1.2', '1.2.3' (optional v/prerelease) into components."""
    m = _PARTIAL_RE.match(text)
    if m is None:
        raise InvalidRange("invalid version in range: %r" % text)
    major, minor, patch, prerelease = m.groups()
    return (
        int(major),
        int(minor) if minor is not None else None,
        int(patch) if patch is not None else None,
        prerelease,
    )


def _version(major, minor, patch, prerelease=None):
    s = "%d.%d.%d" % (major, minor, patch)
    if prerelease:
        s += "-" + prerelease
    return Version(s)


def _bump(major, minor, patch, level):
    if level == "major":
        return _version(major + 1, 0, 0)
    if level == "minor":
        return _version(major, minor + 1, 0)
    return _version(major, minor, patch + 1)


class _Comparator:
    """A list of (op, Version) tests ANDed together."""

    def __init__(self, tests):
        self.tests = tests

    def match(self, version):
        if version.is_prerelease and not self._allows_prerelease(version):
            return False
        for op, ver in self.tests:
            if op == "=" and not (version == ver):
                return False
            if op == ">" and not (version > ver):
                return False
            if op == ">=" and not (version >= ver):
                return False
            if op == "<" and not (version < ver):
                return False
            if op == "<=" and not (version <= ver):
                return False
        return True

    def _allows_prerelease(self, version):
        # npm semantics: a prerelease only matches if some comparator in this
        # set names a prerelease on the same [major, minor, patch] tuple.
        for _, ver in self.tests:
            if ver.is_prerelease and (ver.major, ver.minor, ver.patch) == (
                version.major, version.minor, version.patch
            ):
                return True
        return False


def _caret_tests(major, minor, patch, prerelease):
    # ^1.2.3 := >=1.2.3 <2.0.0 ; ^0.2.3 := >=0.2.3 <0.3.0 ; ^0.0.3 := >=0.0.3 <0.0.4
    lo = _version(major, minor if minor is not None else 0,
                  patch if patch is not None else 0, prerelease)
    if minor is None:
        hi = _bump(major, 0, 0, "major")
    elif patch is None:
        hi = _bump(major, minor, 0, "major") if major != 0 else _bump(major, minor, 0, "minor")
    elif major != 0:
        hi = _bump(major, minor, patch, "major")
    elif minor != 0:
        hi = _bump(major, minor, patch, "minor")
    else:
        hi = _bump(major, minor, patch, "patch")
    return [(">=", lo), ("<", hi)]


def _tilde_tests(major, minor, patch, prerelease):
    # ~1.2.3 := >=1.2.3 <1.3.0 ; ~1.2 := >=1.2.0 <1.3.0 ; ~1 := >=1.0.0 <2.0.0
    lo = _version(major, minor if minor is not None else 0,
                  patch if patch is not None else 0, prerelease)
    if minor is None:
        hi = _bump(major, 0, 0, "major")
    else:
        hi = _bump(major, minor, 0, "minor")
    return [(">=", lo), ("<", hi)]


def _simple_tests(op, major, minor, patch, prerelease):
    if op in (None, "="):
        if minor is None:
            return [(">=", _version(major, 0, 0)), ("<", _bump(major, 0, 0, "major"))]
        if patch is None:
            return [(">=", _version(major, minor, 0)), ("<", _bump(major, minor, 0, "minor"))]
        return [("=", _version(major, minor, patch, prerelease))]
    # Partial versions with inequalities expand to the wildcard boundary.
    if minor is None:
        boundary = _version(major, 0, 0)
        if op == ">":
            return [(">=", _bump(major, 0, 0, "major"))]
        if op == ">=":
            return [(">=", boundary)]
        if op == "<":
            return [("<", boundary)]
        return [("<", _bump(major, 0, 0, "major"))]
    if patch is None:
        boundary = _version(major, minor, 0)
        if op == ">":
            return [(">=", _bump(major, minor, 0, "minor"))]
        if op == ">=":
            return [(">=", boundary)]
        if op == "<":
            return [("<", boundary)]
        return [("<", _bump(major, minor, 0, "minor"))]
    return [(op, _version(major, minor, patch, prerelease))]


def _parse_comparator_set(text):
    tests = []
    for token in text.split():
        if token.startswith("^"):
            tests.extend(_caret_tests(*_parse_partial(token[1:])))
        elif token.startswith("~"):
            tests.extend(_tilde_tests(*_parse_partial(token[1:])))
        else:
            op, rest = _OP_RE.match(token).groups()
            tests.extend(_simple_tests(op, *_parse_partial(rest)))
    if not tests:
        raise InvalidRange("empty comparator set")
    return _Comparator(tests)


class Range:
    """A version range: space-ANDed comparators, joined by || (OR)."""

    def __init__(self, text):
        if not isinstance(text, str) or not text.strip():
            raise InvalidRange("range must be a non-empty string")
        self._sets = [_parse_comparator_set(part) for part in text.split("||")]
        self._text = text

    def match(self, version):
        """Return True if `version` satisfies any comparator set."""
        if not isinstance(version, Version):
            version = Version(version)
        return any(s.match(version) for s in self._sets)

    def __contains__(self, version):
        return self.match(version)

    def __repr__(self):
        return "Range(%r)" % self._text
