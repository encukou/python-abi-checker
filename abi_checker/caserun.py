from functools import cached_property
import dataclasses
import tempfile
import asyncio
import shlex
import enum
import os

from .case import Case
from .util import cached_task
from .build import Build
from .errors import SkipBuild
from .pyversion import PyVersion
from .compileoptions import CompileOptions


class RunResult(enum.Enum):
    SUCCESS = 'success', '✅'
    BUILD_FAILURE = 'build failure', '⛔'
    EXEC_FAILURE = 'exec failure', '❌'
    SKIP = 'skip', '〰️'
    ERROR = 'error', '☠️'

    def __new__(cls, value, emoji):
        self = object.__new__(cls)
        self._value_ = value
        self.emoji = emoji
        return self


@dataclasses.dataclass
class CaseRun:
    case: Case
    compile_build: Build
    compile_options: CompileOptions
    exec_build: Build

    has_result = False

    def __repr__(self):
        return f'<CaseRun {self.case.name} comp={self.compile_build!s} exec={self.exec_build!s}>'

    @cached_task
    async def get_result(self):
        try:
            await self.case.verify_compatibility(self)
            proc = await self.compile()
            if proc.returncode != 0:
                self.exception = None
                self.has_result = True
                return RunResult.BUILD_FAILURE
            proc = await self.exec()
            if proc.returncode != 0:
                self.exception = None
                self.has_result = True
                return RunResult.EXEC_FAILURE
        except SkipBuild as e:
            self.exception = e
            self.has_result = True
            return RunResult.SKIP
        except Exception as e:
            self.exception = e
            self.has_result = True
            return RunResult.ERROR

        self.exception = None
        return RunResult.SUCCESS

    @cached_task
    async def get_flags(self):
        build = self.compile_build
        flags = shlex.split(
            await build.run_pyconfig('--cflags', '--ldflags'),
        )
        flags.extend(self.compile_options.cflags)
        for feature in build.features:
            flags.extend(feature.cflags)
        flags.append(f'-I{self.case.path}')
        return flags

    async def compile(self):
        build = self.compile_build
        cc = await build.get_config_var('CC')
        flags = await self.get_flags()
        self.extension_module_path.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = await self.root.run_process(
                cc, *flags, '--shared',
                self.case.extension_source_path,
                '-o', self.extension_module_path,
                '-fPIC',
                stdout=self.path / 'compile.log',
                stderr=self.path / 'compile.log',
                cwd=tmpdir,
                check=False,
            )
        return proc

    async def exec(self):
        build = self.exec_build
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = await build.run_python(
                self.case.py_script_path,
                cwd=tmpdir,
                stdout=self.path / 'stdout.log',
                stderr=self.path / 'stderr.log',
                env={**os.environ, 'PYTHONPATH': self.path},
                check=False,
            )
        return proc

    @cached_property
    def root(self):
        return self.case.root

    @cached_property
    def path(self):
        return (
            self.root.cache_dir
            / 'runs'
            / self.case.tag
            / self.compile_build.tag
            / self.compile_options.tag
            / self.exec_build.tag
        )

    @cached_property
    def extension_module_path(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path / 'extension.so'
