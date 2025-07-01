from functools import cached_property
from pathlib import Path
import dataclasses
import asyncio
import tomllib
import shlex
import os

from .build import Build
from .errors import SkipBuild
from .pyversion import PyVersion


class Cases:
    def __init__(self, path):
        self.paths = {path.name: path for path in sorted(path.glob('*/'))}
        self._cases = {}

    def __len__(self):
        return len(self.paths)

    def __iter__(self):
        return iter(self.paths.keys())

    def __getitem__(self, name):
        try:
            return self._cases[name]
        except KeyError:
            case = Case(self.paths[name])
            self._cases[name] = case
            return case


class Case:
    def __init__(self, path):
        self.path = path

    @cached_property
    def data(self):
        with (self.path / 'case.toml').open('rb') as file:
            return tomllib.load(file)

    @cached_property
    def compile_build_spec(self):
        return BuildPythonSpec.from_dict(self.data.get('build-python', {}))

    @cached_property
    def run_build_spec(self):
        return BuildPythonSpec.from_dict(self.data.get('build-python', {}))

    @cached_property
    def extension_source_path(self):
        return self.path / 'extension.c'

    @cached_property
    def py_script_path(self):
        return self.path / 'script.py'

    @cached_property
    def tag(self):
        return self.path.name


@dataclasses.dataclass
class CaseRun:
    cache_dir: Path
    case: Case
    compile_build: Build
    run_build: Build

    async def __call__(self):
        await self.compile(self.compile_build)
        return await self.exec(self.run_build)

    async def compile(self, build):
        await self.case.compile_build_spec.verify_compatibility(build)
        cc = await build.get_config_var('CC')
        flags = await build.run_pyconfig('--cflags', '--ldflags')
        proc = await asyncio.create_subprocess_exec(
            cc, *shlex.split(flags), '--shared',
            self.case.extension_source_path,
            '-o', self.extension_module_path,
            '-fPIC',
            cwd=build.worktree_dir,
        )
        await proc.communicate()
        assert proc.returncode == 0
        return self.extension_module_path

    async def exec(self, build):
        await self.case.run_build_spec.verify_compatibility(build)
        proc = await build.run_python(
            self.case.py_script_path,
            cwd=build.worktree_dir,
            env={**os.environ, 'PYTHONPATH': self.path},
        )
        await proc.communicate()
        assert proc.returncode == 0

    @cached_property
    def path(self):
        return self.cache_dir / '_'.join((
            'run',
            self.case.tag,
            self.compile_build.tag,
            self.run_build.tag,
        ))

    @cached_property
    def extension_module_path(self):
        self.path.mkdir(exist_ok=True)
        return self.path / 'extension.so'


@dataclasses.dataclass
class BuildPythonSpec():
    minimum: PyVersion = None

    @classmethod
    def from_dict(cls, d):
        args = {}
        if ver := d.get('version'):
            if minimum := ver.get('min'):
                args['minimum'] = PyVersion.parse(minimum)
        return cls(**args)

    async def verify_compatibility(self, build):
        print(self.minimum, build)
        if self.minimum and self.minimum > (await build.get_version()):
            raise SkipBuild(f'requires {self.minimum}')
