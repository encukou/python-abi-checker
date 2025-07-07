import collections
import subprocess
import asyncio
import shlex
import os

from .util import cached_task
from .commit import CPythonCommit
from .pyversion import PyVersion
from .compileoptions import CompileOptions


class Build:
    """A build of CPython"""

    def __init__(self, root, commit, features=()):
        self.root = root
        self.commit = commit
        self.features = features
        self.lock = asyncio.Lock()
        self._config_vars = {}

    _version = None

    @property
    def tag(self):
        if not self.features:
            return self.commit.name
        return self.commit.name + '~' + ''.join(f.tag for f in self.features)

    def __str__(self):
        return self.tag

    def __repr__(self):
        return f'<Build {self}>'

    async def run_python(self, *args, **kwargs):
        executable = await self.get_executable()
        return await self.root.run_process(
            executable, *args, **kwargs,
        )

    @cached_task
    async def get_executable(self):
        build_dir = await self.get_build_dir()
        executable = build_dir / 'python'
        if executable.exists():
            return executable
        await self.configure()
        async with self.lock:
            if executable.exists():
                return executable
            await self.root.run_process(
                'make',
                '-j', str(os.process_cpu_count() or 2),
                stdout=build_dir / 'make.log',
                stderr=build_dir / 'make.log',
                cwd=build_dir,
            )
            version = await self._get_version(executable)
            if version > PyVersion.pack(3, 7):
                await self.root.run_process(
                    'make', 'pythoninfo',
                    stdout=build_dir / 'pythoninfo',
                    cwd=build_dir,
                )
        return executable

    @cached_task
    async def configure(self):
        build_dir = await self.get_build_dir()
        makefile_path = build_dir / 'Makefile'
        if makefile_path.exists():
            return
        for feature in self.features:
            await feature.verify_compatibility(self.commit)
        worktree = await self.commit.get_worktree()
        async with self.lock:
            if makefile_path.exists():
                return
            build_dir.mkdir(exist_ok=True)
            config_options = []
            for feature in self.features:
                config_options.extend(feature.config_options)
            await self.root.run_process(
                worktree / 'configure',
                *config_options,
                stdout=await self.get_config_log_path(),
                stderr=await self.get_config_log_path(),
                cwd=build_dir,
            )

    @cached_task
    async def get_build_dir(self):
        chash = await self.commit.get_commit_hash()
        return self.root.cache_dir / f'build-{self.tag}-{chash}'

    @cached_task
    async def get_config_log_path(self):
        build_dir = await self.get_build_dir()
        return build_dir / '_config.log'

    async def get_config_var(self, var):
        proc = await self.run_python(
            '-c',
            f'import sysconfig; print(sysconfig.get_config_var({var!r}))',
            stdout=subprocess.PIPE,
        )
        return proc.stdout_data.decode().strip()

    async def run_pyconfig(self, *args):
        build_dir = await self.get_build_dir()
        proc = await self.run_python(
            build_dir / 'python-config.py',
            *args,
            stdout=subprocess.PIPE,
        )
        return proc.stdout_data.decode().strip()

    @cached_task
    async def get_flags(self):
        return tuple(shlex.split(
            await self.run_pyconfig('--cflags', '--ldflags'),
        ))

    @cached_task
    async def get_compiler(self):
        return await self.get_config_var('CC')

    @cached_task
    async def get_version(self):
        executable = await self.get_executable()
        return await self._get_version(executable)

    async def _get_version(self, executable):
        proc = await self.root.run_process(
            executable,
            '-c',
            f'import sys; print(sys.hexversion)',
            stdout=subprocess.PIPE,
        )
        return PyVersion.from_hex(int(proc.stdout_data.decode()))

    @cached_task
    async def get_possible_compile_options(self):
        result = []
        result.append(CompileOptions(None))
        result.append(CompileOptions(3))
        version = await self.commit.get_version()
        for i in range(9, version.minor + 1):
            result.append(CompileOptions((3<<24) | (i<<16)))
        return result
