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
        if self.minimum and self.minimum > (await build.get_version()):
            raise SkipBuild(f'requires {self.minimum}')
