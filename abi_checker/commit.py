from functools import cached_property
import dataclasses
import subprocess
import asyncio
import re

from .root import Root
from .util import cached_task
from .pyversion import PyVersion

readme_re = re.compile(rb"This is Python version (?P<version>[\.\da-z]+)")

@dataclasses.dataclass
class CPythonCommit:
    root: Root
    name: str

    _commit_hash = None
    _version = None

    @cached_task
    async def get_worktree(self):
        commit_hash = await self.get_commit_hash()
        worktree_dir = self.root.cache_dir / f'cpython_{commit_hash}'
        for try_count in range(5):
            if worktree_dir.exists():
                return worktree_dir
            proc = await self.root.run_process(
                'git', 'worktree', 'add',
                '--detach', '--checkout',
                worktree_dir,
                await self.get_commit_hash(),
                cwd=await self.root.get_cloned_repo(),
                check=False,
            )
            if proc.returncode == 0:
                break
            elif proc.returncode == 128:
                # Git index is locked?
                await asyncio.sleep(.1 * (2**try_count))
                continue
            assert proc.returncode == 0
        return worktree_dir

    @cached_task
    async def get_commit_hash(self):
        proc = await self.root.run_process(
            'git', 'rev-parse', self.name,
            stdout=subprocess.PIPE,
            cwd=self.root.cpython_dir,
            check=False,
        )
        if proc.returncode == 128:
            return '0' * 40
        assert proc.returncode == 0
        return proc.stdout_data.strip().decode()

    def __hash__(self):
        return hash(self.name)

    @cached_task
    async def get_version(self):
        if self._version is not None:
            return self._version
        commit_hash = await self.get_commit_hash()
        if commit_hash == '0' * 40:
            return PyVersion.from_hex(0)
        for name in 'README.rst', 'README':
            proc = await self.root.run_process(
                'git', 'show', f'{commit_hash}:{name}',
                stdout=subprocess.PIPE,
                cwd=self.root.cpython_dir,
                check=False,
            )
            if proc.returncode == 0:
                break
        else:
            raise LookupError(f'README not found in commit {commit_hash}')
        firstline, sep, rest = proc.stdout_data.partition(b'\n')
        match = readme_re.match(firstline)
        ver_string = match['version'].decode()
        self._version = PyVersion.parse(ver_string)
        return self._version


async def get_tagged_commits(root):
    proc = await root.run_process(
        'git', 'tag',
        stdout=subprocess.PIPE,
        cwd=root.cpython_dir,
    )
    return [
        CPythonCommit(root, line)
        for line in proc.stdout_data.decode().splitlines()
    ]
