from functools import cached_property
import dataclasses
import asyncio
import shlex
import enum
import os

from .case import Case
from .util import cached_task
from .build import Build
from .errors import SkipBuild


class RunResult(enum.Enum):
    SUCCESS = 'success'
    ERROR = 'error'
    FAILURE = 'failure'
    SKIP = 'skip'


@dataclasses.dataclass
class CaseRun:
    case: Case
    compile_build: Build
    exec_build: Build

    _result = None

    def __repr__(self):
        return f'<CaseRun {self.case.name} comp={self.compile_build!s} exec={self.exec_build!s} result={self._result}>'

    @cached_task
    async def get_result(self):
        try:
            await self.compile()
            proc = await self.exec()
        except SkipBuild as e:
            self.exception = e
            return RunResult.SKIP
        except Exception as e:
            self.exception = e
            return RunResult.ERROR

        self.exception = None
        if proc.returncode == 0:
            return RunResult.SUCCESS
        return RunResult.FAILURE

    async def compile(self):
        build = self.compile_build
        await self.case.compile_build_spec.verify_compatibility(build)
        cc = await build.get_config_var('CC')
        flags = await self.get_flags()
        await self.root.run_process(
            cc, *flags, '--shared',
            self.case.extension_source_path,
            '-o', self.extension_module_path,
            '-fPIC',
            stdout=self.path / 'compile.log',
            stderr=self.path / 'compile.log',
            cwd=build.build_dir,
        )
        return self.extension_module_path

    @cached_task
    async def get_flags(self):
        build = self.compile_build
        flags = shlex.split(
            await build.run_pyconfig('--cflags', '--ldflags'),
        )
        for feature in build.features:
            flags.extend(feature.cflags)
        flags.append(f'-I{self.case.path}')
        return flags

    async def exec(self):
        build = self.exec_build
        await self.case.run_build_spec.verify_compatibility(build)
        proc = await build.run_python(
            self.case.py_script_path,
            cwd=build.build_dir,
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
            / self.exec_build.tag
        )

    @cached_property
    def extension_module_path(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path / 'extension.so'
