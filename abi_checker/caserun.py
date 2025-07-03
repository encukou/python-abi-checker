from functools import cached_property
import dataclasses
import asyncio
import shlex
import enum
import os

from .case import Case
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

    async def get_result(self):
        if self._result is not None:
            return self._result
        async with self.lock:
            if self._result is not None:
                return self._result
            try:
                await self.compile()
                proc = await self.exec()
            except SkipBuild as e:
                self._result = RunResult.SKIP
                self.exception = e
            except Exception as e:
                self._result = RunResult.ERROR
                self.exception = e
            else:
                if proc.returncode == 0:
                    self._result = RunResult.SUCCESS
                else:
                    self._result = RunResult.FAILURE
                self.exception = None
        return self._result

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
            cwd=build.build_dir,
        )
        return self.extension_module_path

    async def get_flags(self):
        build = self.compile_build
        flags = shlex.split(
            await build.run_pyconfig('--cflags', '--ldflags'),
        )
        for feature in build.features:
            flags.extend(feature.cflags)
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
    def lock(self):
        return asyncio.Lock()

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
