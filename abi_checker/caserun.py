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
    run_build: Build

    _result = None

    def __repr__(self):
        return f'<CaseRun {self.case.name} comp={self.compile_build!s} run={self.run_build!s} result={self._result}>'

    async def get_result(self):
        if self._result is not None:
            return self._result
        async with self.lock:
            if self._result is not None:
                return self._result
            try:
                await self.compile(self.compile_build)
                proc = await self.exec(self.run_build)
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

    async def compile(self, build):
        await self.case.compile_build_spec.verify_compatibility(build)
        cc = await build.get_config_var('CC')
        flags = await build.run_pyconfig('--cflags', '--ldflags')
        await self.root.run_process(
            cc, *shlex.split(flags), '--shared',
            self.case.extension_source_path,
            '-o', self.extension_module_path,
            '-fPIC',
            cwd=build.build_dir,
        )
        return self.extension_module_path

    async def exec(self, build):
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
            / self.run_build.tag
        )

    @cached_property
    def extension_module_path(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path / 'extension.so'
