from pathlib import Path
import subprocess
import argparse
import asyncio
import sys

from .pyversion import PyVersion, get_latest_branch_releases
from .errors import SkipBuild
from .build import Build
from .case import Cases, CaseRun

async def get_tagged_versions(cpython_dir):
    proc = await asyncio.create_subprocess_exec(
        'git', 'tag',
        stdout=subprocess.PIPE,
        cwd=cpython_dir,
    )
    result = {}
    async for line in proc.stdout:
        if line.startswith(b'v3'):
            tag = line.decode().strip()
            try:
                version = PyVersion.parse(tag[1:])
            except ValueError:
                pass
            else:
                result[version] = tag
    await proc.communicate()
    assert proc.returncode == 0
    return result


async def get_cloned_repo(cpython_dir, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = cache_dir / 'cpython.git'
    if repo_dir.exists():
        proc = await asyncio.create_subprocess_exec(
            'git', 'fetch', 'origin',
            cwd=repo_dir,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            'git', 'clone',
            '--bare',
            '--', cpython_dir, repo_dir,
        )
    await proc.communicate()
    assert proc.returncode == 0

    return repo_dir


def resolved_path(*p):
    return Path(*p).resolve()


async def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0])
    parser.add_argument(
        'cpython_dir', metavar='CPYTHON_DIR',
        help='CPYthon Git URL, or directory with source checkout')
    parser.add_argument(
        '--cache_dir',
        type=resolved_path,
        default=resolved_path('.cache'),
        help='Cache directory (large).')
    parser.add_argument(
        '--case_dir',
        type=resolved_path,
        default=resolved_path(__file__, '../cases'),
        help='Directory of cases.')

    args = parser.parse_args(argv[1:])

    async with asyncio.TaskGroup() as tg:
        versions_task = tg.create_task(get_tagged_versions(args.cpython_dir))
        cloned_repo_task = tg.create_task(get_cloned_repo(args.cpython_dir, args.cache_dir))

    versions = get_latest_branch_releases((await versions_task).keys())[-6:]

    cases = Cases(args.case_dir)

    print(cases)
    case = cases['tutorial-simple-3.13']

    tasks = {}
    for version in versions:
        build = Build(f'v{version}', repo_dir=cloned_repo_task.result(), cache_dir=args.cache_dir)
        run = CaseRun(args.cache_dir, case, build, build)
        tasks[version] = asyncio.create_task(run())

    for version, task in tasks.items():
        try:
            result = await task
        except SkipBuild:
            print('skip:', version)
        else:
            print(result)

    print('ok')
