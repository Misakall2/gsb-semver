"""SemVer 2.0 version parsing and comparison."""

import re
from functools import total_ordering

# SemVer 2.0 official regex (https://semver.org), with optional leading "v".
_VERSION_RE = re.compile(
    r"^v?"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r"$"
)


class InvalidVersion(ValueError):
    """Raised when a string is not a valid SemVer 2.0 version."""


def _parse_prerelease(text):
    if text is None:
        return ()
    parts = []
    for ident in text.split("."):
        if ident.isdigit():
            parts.append((0, int(ident), ""))
        else:
            parts.append((1, 0, ident))
    return tuple(parts)


@total_ordering
class Version:
    """An immutable SemVer 2.0 version.

    Build metadata is stored but ignored for precedence and equality.
    """

    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, text):
        if isinstance(text, Version):
            self.major = text.major
            self.minor = text.minor
            self.patch = text.patch
            self.prerelease = text.prerelease
            self.build = text.build
            return
        if not isinstance(text, str):
            raise InvalidVersion("version must be a string, got %r" % type(text).__name__)
        m = _VERSION_RE.match(text.strip())
        if m is None:
            raise InvalidVersion("invalid SemVer 2.0 version: %r" % text)
        self.major = int(m.group("major"))
        self.minor = int(m.group("minor"))
        self.patch = int(m.group("patch"))
        self.prerelease = _parse_prerelease(m.group("prerelease"))
        self.build = m.group("build") or ""

    @property
    def is_prerelease(self):
        return bool(self.prerelease)

    def _key(self):
        # A release sorts after any of its prereleases.
        if self.prerelease:
            return (self.major, self.minor, self.patch, 0, self.prerelease)
        return (self.major, self.minor, self.patch, 1, ())

    def __eq__(self, other):
        if not isinstance(other, Version):
            try:
                other = Version(other)
            except (InvalidVersion, TypeError):
                return NotImplemented
        return self._key() == other._key()

    def __lt__(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        return self._key() < other._key()

    def __hash__(self):
        return hash(self._key())

    def __str__(self):
        s = "%d.%d.%d" % (self.major, self.minor, self.patch)
        if self.prerelease:
            idents = []
            for kind, num, text in self.prerelease:
                idents.append(str(num) if kind == 0 else text)
            s += "-" + ".".join(idents)
        if self.build:
            s += "+" + self.build
        return s

    def __repr__(self):
        return "Version(%r)" % str(self)
