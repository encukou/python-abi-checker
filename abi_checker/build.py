import collections
import subprocess
import asyncio
import os

from .util import cached_task
from .commit import CPythonCommit
from .pyversion import PyVersion


class Build:
    """A build of CPython"""

    def __init__(self, root, commit, features=()):
        self.root = root
        self.commit = commit
        self.features = features
        self.lock = asyncio.Lock()
        self.build_dir = root.cache_dir / f'build_{self.tag}'
        self.config_log_path = self.build_dir / '_config.log'

    _version = None

    @property
    def tag(self):
        return self.commit.name + ''.join(f.tag for f in self.features)

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
        executable = self.build_dir / 'python'
        if executable.exists():
            return executable
        await self.configure()
        async with self.lock:
            if executable.exists():
                return executable
            await self.root.run_process(
                'make',
                '-j', str(os.process_cpu_count() or 2),
                cwd=self.build_dir,
            )
            await self.root.run_process(
                'make', 'pythoninfo',
                stdout=self.build_dir / 'pythoninfo',
                cwd=self.build_dir,
            )
        return executable

    @cached_task
    async def configure(self):
        makefile_path = self.build_dir / 'Makefile'
        if makefile_path.exists():
            return
        for feature in self.features:
            await feature.verify_compatibility(self.commit)
        worktree = await self.commit.get_worktree()
        async with self.lock:
            if makefile_path.exists():
                return
            self.build_dir.mkdir(exist_ok=True)
            config_options = []
            for feature in self.features:
                config_options.extend(feature.config_options)
            await self.root.run_process(
                worktree / 'configure',
                *config_options,
                stdout=self.config_log_path,
                stderr=self.config_log_path,
                cwd=self.build_dir,
            )

    async def get_config_var(self, var):
        proc = await self.run_python(
            '-c',
            f'import sysconfig; print(sysconfig.get_config_var({var!r}))',
            stdout=subprocess.PIPE,
        )
        return proc.stdout_data.decode().strip()

    async def run_pyconfig(self, *args):
        proc = await self.run_python(
            self.build_dir / 'python-config.py',
            *args,
            stdout=subprocess.PIPE,
        )
        return proc.stdout_data.decode().strip()

    @cached_task
    async def get_version(self):
        proc = await self.run_python(
            '-c',
            f'import sys; print(sys.hexversion)',
            stdout=subprocess.PIPE,
        )
        return PyVersion.from_hex(int(proc.stdout_data.decode()))
