"""Semantic Versioning 2.0.0 parsing, comparison, and range matching.

Standard library only. Usage:

    from semverlib import Version, Range, parse

    parse("v1.2.0-alpha.1+build")      # leading v tolerated, build ignored in cmp
    Version(1, 0, 0, "alpha") < Version(1, 0, 0)
    Range(">=1.0.0 <2 || ^3.1.0").matches(parse("3.2.0"))
"""

import re

__all__ = ["Version", "Range", "InvalidVersion", "InvalidRange", "parse", "compare"]

_SEMVER_RE = re.compile(
    r"^v?"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class InvalidVersion(ValueError):
    """Raised when a version string does not conform to SemVer 2.0.0."""


class InvalidRange(ValueError):
    """Raised when a range expression cannot be parsed."""


def _cmp(a, b):
    return (a > b) - (a < b)


def _compare_prerelease(a, b):
    # a/b are tuples of identifiers or None (no prerelease).
    if a is None and b is None:
        return 0
    if a is None:  # release > any prerelease
        return 1
    if b is None:
        return -1
    for x, y in zip(a, b):
        if x == y:
            continue
        x_num, y_num = x.isdigit(), y.isdigit()
        if x_num and y_num:
            return _cmp(int(x), int(y))
        if x_num:  # numeric identifiers sort lower than alphanumeric
            return -1
        if y_num:
            return 1
        return _cmp(x, y)
    return _cmp(len(a), len(b))  # shorter set sorts lower


class Version:
    """An immutable SemVer 2.0.0 version. Build metadata is ignored in ordering."""

    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease=None, build=None):
        for name, num in (("major", major), ("minor", minor), ("patch", patch)):
            if not isinstance(num, int) or isinstance(num, bool) or num < 0:
                raise InvalidVersion(f"{name} must be a non-negative int, got {num!r}")
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease.split(".")) if prerelease else None
        self.build = build or None

    @classmethod
    def parse(cls, text):
        if not isinstance(text, str):
            raise InvalidVersion(f"version must be a string, got {type(text).__name__}")
        m = _SEMVER_RE.match(text.strip())
        if not m:
            raise InvalidVersion(f"invalid SemVer string: {text!r}")
        return cls(
            int(m.group("major")),
            int(m.group("minor")),
            int(m.group("patch")),
            m.group("prerelease"),
            m.group("build"),
        )

    def _key(self):
        return (self.major, self.minor, self.patch)

    def compare(self, other):
        if not isinstance(other, Version):
            other = Version.parse(other)
        c = _cmp(self._key(), other._key())
        return c if c else _compare_prerelease(self.prerelease, other.prerelease)

    def __eq__(self, other):
        if not isinstance(other, Version):
            try:
                other = Version.parse(other)
            except InvalidVersion:
                return NotImplemented
        return self.compare(other) == 0

    def __ne__(self, other):
        eq = self.__eq__(other)
        return eq if eq is NotImplemented else not eq

    def __lt__(self, other):
        return self.compare(other) < 0

    def __le__(self, other):
        return self.compare(other) <= 0

    def __gt__(self, other):
        return self.compare(other) > 0

    def __ge__(self, other):
        return self.compare(other) >= 0

    def __hash__(self):
        return hash((self._key(), self.prerelease))

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + ".".join(self.prerelease)
        if self.build:
            s += "+" + self.build
        return s

    def __repr__(self):
        return f"Version({str(self)!r})"


def parse(text):
    return Version.parse(text)


def compare(a, b):
    return Version.parse(a).compare(b) if isinstance(a, str) else a.compare(b)


class _Comparator:
    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def matches(self, v):
        c = v.compare(self.version)
        return {
            "=": c == 0,
            "==": c == 0,
            "!=": c != 0,
            "<": c < 0,
            "<=": c <= 0,
            ">": c > 0,
            ">=": c >= 0,
        }[self.op]


_COMPARATOR_RE = re.compile(
    r"^(?P<op><=|>=|==|!=|=|<|>)?\s*(?P<ver>\S+)$"
)


def _caret_bounds(v):
    # ^1.2.3 := >=1.2.3 <2.0.0 ; ^0.2.3 := >=0.2.3 <0.3.0 ; ^0.0.3 := >=0.0.3 <0.0.4
    if v.major > 0:
        upper = Version(v.major + 1, 0, 0)
    elif v.minor > 0:
        upper = Version(0, v.minor + 1, 0)
    else:
        upper = Version(0, 0, v.patch + 1)
    return v, upper


def _tilde_bounds(v):
    # ~1.2.3 := >=1.2.3 <1.3.0
    return v, Version(v.major, v.minor + 1, 0)


_PARTIAL_RE = re.compile(r"^v?(\d+)(?:\.(\d+)(?:\.(\d+))?)?$")


def _parse_partial(text):
    """Parse '2' or '1.2' into a Version, padding missing parts with 0.

    Only used inside range expressions; bare Version.parse stays strict.
    """
    try:
        return Version.parse(text)
    except InvalidVersion:
        m = _PARTIAL_RE.match(text)
        if not m:
            raise
        parts = [int(p) if p is not None else 0 for p in m.groups()]
        return Version(*parts)


class _AndSet:
    """A conjunction of comparators (one whitespace-separated clause)."""

    __slots__ = ("comparators",)

    def __init__(self, comparators):
        self.comparators = comparators

    def matches(self, v):
        return all(c.matches(v) for c in self.comparators)


def _parse_clause(clause):
    comparators = []
    for token in clause.split():
        if token.startswith("^"):
            lo, hi = _caret_bounds(_parse_partial(token[1:]))
            comparators.append(_Comparator(">=", lo))
            comparators.append(_Comparator("<", hi))
        elif token.startswith("~"):
            lo, hi = _tilde_bounds(_parse_partial(token[1:]))
            comparators.append(_Comparator(">=", lo))
            comparators.append(_Comparator("<", hi))
        else:
            m = _COMPARATOR_RE.match(token)
            if not m:
                raise InvalidRange(f"cannot parse comparator: {token!r}")
            op = m.group("op") or "="
            try:
                ver = _parse_partial(m.group("ver"))
            except InvalidVersion as e:
                raise InvalidRange(str(e)) from e
            comparators.append(_Comparator(op, ver))
    if not comparators:
        raise InvalidRange("empty range clause")
    return _AndSet(comparators)


class Range:
    """A version range: clauses joined by '||', comparators ANDed within a clause."""

    __slots__ = ("clauses",)

    def __init__(self, expr):
        if not isinstance(expr, str) or not expr.strip():
            raise InvalidRange("range expression must be a non-empty string")
        self.clauses = [_parse_clause(part) for part in expr.split("||")]

    def matches(self, version):
        if not isinstance(version, Version):
            version = Version.parse(version)
        return any(c.matches(version) for c in self.clauses)

    def __contains__(self, version):
        return self.matches(version)

    def __repr__(self):
        return f"Range({self!s})"

    def __str__(self):
        return " || ".join(
            " ".join(f"{c.op}{c.version}" for c in clause.comparators)
            for clause in self.clauses
        )
