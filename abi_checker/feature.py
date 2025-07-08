
from .errors import SkipBuild
from .pyversion import PyVersion

class Feature:
    tag: str
    config_options: tuple = ()
    cflags: tuple = ()

    async def verify_compatibility(self, commit):
        pass

    async def verify_opt_compatibility(self, options):
        pass


class FreeThreading(Feature):
    tag = 't'
    config_options = ('--disable-gil',)
    cflags = ('-DPy_GIL_DISABLED=1',)
    min_version = PyVersion(3, 13)

    async def verify_compatibility(self, build):
        commit_version = await build.commit.get_version()
        if commit_version < PyVersion(3, 13):
            raise SkipBuild(
                f'{self.tag!r} not compatible with {commit_version}'
            )

    async def verify_option_compatibility(self, build, opts):
        commit_version = await build.commit.get_version()
        if opts.is_limited_api and commit_version < PyVersion(3, 15):
            raise SkipBuild(
                f'{self.tag!r} not compatible with limited API'
            )

_FEATURES = {
    't': FreeThreading(),
}
