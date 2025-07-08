from functools import cached_property
import dataclasses
import tempfile
import asyncio
import os

from .util import cached_task
from .build import Build
from .errors import ExpectFailure, SkipBuild
from .pyversion import PyVersion
from .runresult import RunResult
from .testmodule import TestModule



@dataclasses.dataclass
class CaseRun:
    test_module: TestModule
    exec_build: Build

    exception = None

    def __repr__(self):
        return f'<CaseRun {self.case.name} comp={self.compile_build!s} exec={self.exec_build!s}>'

    @classmethod
    def create(cls, case, compile_build, compile_options, exec_build):
        test_module = TestModule(case, compile_build, compile_options)
        return cls(test_module, exec_build)

    @cached_task
    async def get_result(self):
        expect_fail = None
        try:
            await self.verify_compatibility()
        except SkipBuild as e:
            self.exception = e
            return RunResult.SKIPPED
        except ExpectFailure as e:
            expect_fail = e
        real_result = await self._get_real_result()
        if real_result == RunResult.ERROR:
            return real_result
        try:
            if expect_fail is not None:
                if real_result == RunResult.SUCCESS:
                    self.exception = expect_fail
                    return RunResult.UNEXPECTED_SUCCESS
                return RunResult.EXPECTED_FAILURE
            else:
                return real_result
        except Exception as e:
            self.exception = e
        return RunResult.ERROR

    async def _get_real_result(self):
        try:
            result = await self.test_module.get_result()
            if result != RunResult.SUCCESS:
                return result
            proc = await self.exec()
            if proc.returncode != 0:
                return RunResult.EXEC_FAILURE
        except Exception as e:
            self.exception = e
            return RunResult.ERROR
        return RunResult.SUCCESS

    async def exec(self):
        self.path.mkdir(parents=True, exist_ok=True)
        build = self.exec_build
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = await build.run_python(
                self.case.py_script_path,
                cwd=tmpdir,
                stdout=self.path / 'stdout.log',
                stderr=self.path / 'stderr.log',
                env={**os.environ, 'PYTHONPATH': self.test_module.path},
                check=False,
            )
        return proc

    @cached_property
    def root(self):
        return self.test_module.root

    @cached_property
    def case(self):
        return self.test_module.case

    @cached_property
    def compile_build(self):
        return self.test_module.compile_build

    @cached_property
    def compile_options(self):
        return self.test_module.compile_options

    @cached_property
    def extension_module_path(self):
        return self.test_module.extension_module_path

    @property
    def has_result(self):
        return self.get_result.task.done()

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

    @cached_task
    async def verify_compatibility(self):
        exec_version = await self.exec_build.get_version()
        if self.compile_options.is_limited_api:
            if self.compile_options.limited_api >= exec_version.hex:
                raise SkipBuild('limited API larger than exec version')
        script = self.case.compatibility_script
        exec(script, dict(
            compile_version=await self.compile_build.get_version(),
            exec_version=exec_version,
            compile_features=[f.tag for f in self.compile_build.features],
            exec_features=[f.tag for f in self.exec_build.features],
            is_limited_api=self.compile_options.is_limited_api,
            limited_api=self.compile_options.limited_api_pyversion,
            v=PyVersion.pack,
            ExpectFailure=ExpectFailure,
        ))
