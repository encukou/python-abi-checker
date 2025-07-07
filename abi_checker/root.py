from functools import cached_property
from pathlib import Path
import collections
import dataclasses
import contextlib
import asyncio
import types
import os

from .util import cached_task
from .feature import _FEATURES


@dataclasses.dataclass
class Root:
    cpython_dir: Path
    cache_dir: Path
    case_dir: Path

    @classmethod
    def from_args(cls, args):
        return cls(
            cpython_dir=Path(args.cpython_dir).resolve(),
            cache_dir=Path(args.cache_dir).resolve(),
            case_dir=Path(args.case_dir).resolve(),
        )

    @classmethod
    def from_env(cls, env):
        return cls(
            cpython_dir=Path(env['CPYTHON_DIR']).resolve(),
            cache_dir=Path('.cache').resolve(),
            case_dir=Path(__file__, '../cases').resolve(),
        )

    @cached_property
    def process_semaphore(self):
        return asyncio.Semaphore(os.process_cpu_count() or 2)

    @cached_property
    def _builds(self):
        return {}

    @cached_task
    async def get_cloned_repo(self):
        repo_dir = self.cache_dir / 'cpython.git'
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        if repo_dir.exists():
            await self.run_process(
                'git', 'fetch', 'origin',
                cwd=repo_dir,
            )
        else:
            await self.run_process(
                'git', 'clone',
                '--bare',
                '--', self.cpython_dir, repo_dir,
            )

        return repo_dir

    async def run_process(
        self, *args, check=True, input=None, stdout=None, stderr=None,
        **kwargs
    ):
        stdout_path = stderr_path = None
        async with contextlib.AsyncExitStack() as cm:
            await cm.enter_async_context(self.process_semaphore)
            if isinstance(stdout, Path):
                stdout_path = stdout
                stdout = cm.enter_context(stdout.open('wb'))
            if isinstance(stderr, Path):
                stderr_path = stderr
                if stderr == stdout_path:
                    stderr = stdout
                else:
                    stderr = cm.enter_context(stderr.open('wb'))
            print('starting:', args)
            proc = await asyncio.create_subprocess_exec(
                *args,
                **kwargs,
                stdout=stdout,
                stderr=stderr,
            )
        stdout_data, stderr_data = await proc.communicate(input)
        print('done    :', args)
        if check and proc.returncode != 0:
            exc = AssertionError(f'process {args} returned {proc.returncode}')
            if stdout_path:
                exc.add_note(f'stdout: {stdout_path}')
            if stderr_path:
                exc.add_note(f'stderr: {stderr_path}')
            raise exc
        return types.SimpleNamespace(
            stdout_data=stdout_data,
            stderr_data=stderr_data,
            returncode=proc.returncode,
        )

    async def get_feature(self, tag):
        return _FEATURES[tag]
