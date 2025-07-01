import dataclasses
import collections
import enum
import re

class Level(enum.Enum):
    ALPHA = 'a'
    BETA = 'b'
    CANDIDATE = 'rc'
    FINAL = 'f'

    def __lt__(self, other):
        return self.value < other.value

    @classmethod
    def from_hex(cls, num):
        return cls({
            0xa: 'a',
            0xb: 'b',
            0xc: 'rc',
            0xf: 'f',
            0: 'f',
        }[num])


version_re = re.compile(r'''
    (?P<major>\d+)
    \.
    (?P<minor>\d+)
    (
        \.
        (?P<micro>\d+)
        (
            (?P<releaselevel>a|b|rc|f)
            (?P<serial>\d+)
        )?
    )?
''', re.VERBOSE)


@dataclasses.dataclass(frozen=True, order=True)
class PyVersion:
    major: int
    minor: int
    micro: int = 0
    releaselevel: Level = Level.FINAL
    serial: int = 0

    @classmethod
    def parse(cls, string):
        match = version_re.fullmatch(string)
        if not match:
            raise ValueError(string)
        parts = {
            name: cls.__annotations__[name](value)
            for name, value in match.groupdict().items()
            if value is not None
        }
        self = cls(**parts)
        return self

    @classmethod
    def from_hex(cls, hexversion):
        return cls(
            major = (hexversion >> 24) & 0xff,
            minor = (hexversion >> 16) & 0xff,
            micro = (hexversion >> 8) & 0xff,
            releaselevel = Level.from_hex((hexversion >> 4) & 0xf),
            serial = hexversion & 0xf,
        )

    def __str__(self):
        parts = [f'{self.major}.{self.minor}.{self.micro}']
        if self.releaselevel != Level.FINAL or self.serial:
            parts.append(f'{self.releaselevel.value}{self.serial}')
        return ''.join(parts)

    def __repr__(self):
        return f'<{type(self).__qualname__} {self}>'

    @property
    def is_prerelease(self):
        return self.releaselevel != Level.FINAL


def get_latest_branch_releases(versions):
    versions_by_xy = collections.defaultdict(list)
    for version in versions:
        versions_by_xy[version.major, version.minor].append(version)
    return sorted(
        max(v, key=lambda v: (-v.is_prerelease, v))
        for v in versions_by_xy.values())
