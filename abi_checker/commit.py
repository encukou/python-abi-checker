from functools import cached_property
import dataclasses
import subprocess
import asyncio
import re

from .root import Root
from .pyversion import PyVersion

readme_re = re.compile(rb"This is Python version (?P<version>[\.\da-z]+)")

@dataclasses.dataclass
class CPythonCommit:
    root: Root
    name: str

    _commit_hash = None
    _version = None

    async def get_worktree(self):
        commit_hash = await self.get_commit_hash()
        worktree_dir = self.root.cache_dir / f'cpython_{commit_hash}'
        if worktree_dir.exists():
            return worktree_dir
        async with self.lock:
            if worktree_dir.exists():
                return worktree_dir
            await self.root.run_process(
                'git', 'worktree', 'add',
                '--detach', '--checkout',
                worktree_dir,
                await self.get_commit_hash(),
                cwd=await self.root.get_cloned_repo(),
            )
            return worktree_dir

    async def get_commit_hash(self):
        if self._commit_hash is not None:
            return self._commit_hash
        proc = await self.root.run_process(
            'git', 'rev-parse', self.name,
            stdout=subprocess.PIPE,
            cwd=self.root.cpython_dir,
        )
        self._commit_hash = proc.stdout_data.strip().decode()
        return self._commit_hash

    def __hash__(self):
        return hash(self.name)

    @cached_property
    def lock(self):
        return asyncio.Lock()

    async def get_version(self):
        if self._version is not None:
            return self._version
        commit_hash = await self.get_commit_hash()
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
