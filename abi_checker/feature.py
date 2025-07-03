import dataclasses

from .errors import SkipBuild
from .pyversion import PyVersion

@dataclasses.dataclass(frozen=True)
class Feature:
    tag: str
    config_options: tuple
    min_version: PyVersion = None

    async def verify_compatibility(self, commit):
        commit_version = await commit.get_version()
        if self.min_version and self.min_version > commit_version:
            raise SkipBuild(
                f'{self.tag!r} not compatible with {commit_version}'
            )


_FEATURES = {
    't': Feature(
        't',
        config_options=('--disable-gil',),
        min_version=PyVersion(3, 13),
    ),
}
