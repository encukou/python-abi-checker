from functools import cached_property
from pathlib import Path
import dataclasses
import asyncio
import tomllib

from .root import Root
from .build import Build
from .errors import SkipBuild
from .pyversion import PyVersion


class Cases:
    def __init__(self, root):
        self.root = root
        self._paths = {
            path.name: path
            for path in sorted(root.case_dir.glob('*/'))
        }
        self._cases = {}

    def __len__(self):
        return len(self._paths)

    def __iter__(self):
        return iter(self._paths.keys())

    def __getitem__(self, name):
        try:
            return self._cases[name]
        except KeyError:
            case = Case(self.root, self._paths[name])
            self._cases[name] = case
            return case

    def values(self):
        return [self[name] for name in self._paths]


class Case:
    def __init__(self, root, path):
        self.root = root
        self.path = path

    def __str__(self):
        return self.name

    @cached_property
    def name(self):
        return self.path.name

    @cached_property
    def data(self):
        try:
            file = (self.path / 'case.toml').open('rb')
        except FileNotFoundError:
            return {}
        with file:
            return tomllib.load(file)

    @cached_property
    def compile_build_spec(self):
        return BuildPythonSpec.from_dict(self.data.get('compile-python', {}))

    @cached_property
    def exec_build_spec(self):
        return BuildPythonSpec.from_dict(self.data.get('exec-python', {}))

    @cached_property
    def extension_source_path(self):
        return self.path / 'extension.c'

    @cached_property
    def py_script_path(self):
        return self.path / 'script.py'

    @cached_property
    def tag(self):
        return self.path.name

    async def verify_compatibility(self, run):
        if lim := self.data.get('limited-api'):
            if (req := lim.get('required')) is not None:
                if req:
                    if not run.compile_options.is_limited_api:
                        raise SkipBuild(f'requires limited API')
                else:
                    if run.compile_options.is_limited_api:
                        raise SkipBuild(f'requires non-limited API')
            if run.compile_options.is_limited_api:
                if (ver := lim.get('version')):
                    spec = VersionSpec.from_dict(ver)
                    v = PyVersion.from_hex(run.compile_options.limited_api)
                    await spec.verify_compatibility(v)
        await self.compile_build_spec.verify_compatibility(run.compile_build)
        await self.exec_build_spec.verify_compatibility(run.exec_build)

@dataclasses.dataclass
class VersionSpec():
    minimum: PyVersion | None = None

    @classmethod
    def from_dict(cls, d):
        args = {}
        if minimum := d.get('min'):
            args['minimum'] = PyVersion.parse(minimum)
        return cls(**args)

    async def verify_compatibility(self, version):
        if self.minimum and self.minimum > (version):
            raise SkipBuild(f'requires {self.minimum}')


@dataclasses.dataclass
class BuildPythonSpec():
    version_spec: VersionSpec | None = None

    @classmethod
    def from_dict(cls, d):
        args = {}
        if ver := d.get('version'):
            args['version_spec'] = VersionSpec.from_dict(ver)
        return cls(**args)

    async def verify_compatibility(self, build):
        if self.version_spec:
            version = await build.get_version()
            await self.version_spec.verify_compatibility(version)
