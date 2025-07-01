import collections
import subprocess
import asyncio
import os

from .pyversion import PyVersion


LOCKS = collections.defaultdict(asyncio.Lock)


class Build:
    """A build of CPython"""

    def __init__(self, commit, features=(), *, repo_dir, cache_dir):
        self.commit = commit
        self.features = features
        self.repo_dir = repo_dir
        self.cache_dir = cache_dir
        self.worktree_dir = cache_dir / f'cpython_{self.tag}'

    @property
    def tag(self):
        if not self.features:
            return str(self.commit)
        raise NotImplementedError()

    async def run_python(self, *args, **kwargs):
        executable = await self.get_executable()
        return await asyncio.create_subprocess_exec(executable, *args, **kwargs)

    async def get_executable(self):
        executable = self.worktree_dir / 'python'
        if executable.exists():
            return executable
        await self.configure()
        with LOCKS[self.worktree_dir]:
            if executable.exists():
                return executable
            proc = await asyncio.create_subprocess_exec(
                'make',
                '-j', str(os.process_cpu_count() or 2),
                cwd=self.worktree_dir,
            )
            await proc.communicate()
            assert proc.returncode == 0
            return executable

    async def configure(self):
        if (self.worktree_dir / 'Makefile').exists():
            return
        await self.get_worktree()
        with LOCKS[self.worktree_dir]:
            if (self.worktree_dir / 'Makefile').exists():
                return
            proc = await asyncio.create_subprocess_exec(
                './configure', '-C',
                cwd=self.worktree_dir,
            )
            await proc.communicate()
            assert proc.returncode == 0

    async def get_worktree(self):
        if self.worktree_dir.exists():
            return self.worktree_dir
        with LOCKS[self.worktree_dir]:
            if self.worktree_dir.exists():
                return self.worktree_dir
            proc = await asyncio.create_subprocess_exec(
                'git', 'worktree', 'add',
                '--detach', '--checkout',
                self.worktree_dir,
                self.commit,
                cwd=self.repo_dir,
            )
            await proc.communicate()
            assert proc.returncode == 0
            return self.worktree_dir

    async def get_config_var(self, var):
        proc = await self.run_python(
            '-c',
            f'import sysconfig; print(sysconfig.get_config_var({var!r}))',
            stdout=subprocess.PIPE,
        )
        out, err = await proc.communicate()
        assert proc.returncode == 0
        return out.decode().strip()

    async def run_pyconfig(self, *args):
        proc = await self.run_python(
            self.worktree_dir / 'python-config.py',
            *args,
            stdout=subprocess.PIPE,
        )
        out, err = await proc.communicate()
        assert proc.returncode == 0
        return out.decode().strip()

    async def get_version(self):
        proc = await self.run_python(
            '-c',
            f'import sys; print(sys.hexversion)',
            stdout=subprocess.PIPE,
        )
        out, err = await proc.communicate()
        assert proc.returncode == 0
        return PyVersion.from_hex(int(out.decode().strip()))
