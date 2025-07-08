from functools import cached_property
import dataclasses
import tempfile

from .case import Case
from .util import cached_task
from .build import Build
from .runresult import RunResult
from .compileoptions import CompileOptions


@dataclasses.dataclass
class TestModule:
    case: Case
    compile_build: Build
    compile_options: CompileOptions

    @cached_task
    async def get_result(self):
        proc = await self.compile()
        if proc.returncode != 0:
            return RunResult.BUILD_FAILURE
        return RunResult.SUCCESS

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
        )

    @cached_property
    def extension_module_path(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path / 'extension.so'

    @cached_task
    async def get_flags(self):
        build = self.compile_build
        flags = list(await build.get_flags())
        flags.extend(self.compile_options.cflags)
        for feature in build.features:
            flags.extend(feature.cflags)
        flags.append(f'-I{self.case.path}')
        return flags

    async def compile(self):
        build = self.compile_build
        cc = await build.get_compiler()
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
