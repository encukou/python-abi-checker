from pathlib import Path
import collections
import argparse
import asyncio
import sys

from .root import Root
from .commit import CPythonCommit, get_tagged_commits
from .report import Report
from .errors import SkipBuild
from .pyversion import PyVersion


async def get_latest_branch_releases(root):
    versions_by_xy = collections.defaultdict(list)
    for commit in await get_tagged_commits(root):
        if commit.name.startswith('v3'):
            version = PyVersion.parse(commit.name[1:])
            key = version.major, version.minor
            versions_by_xy[key].append((version, commit))
    best_versions_and_commits = sorted(
        max(vcs, key=lambda vc: (-vc[0].is_prerelease, vc))
        for vcs in versions_by_xy.values()
    )
    return [
        commit
        for version, commit
        in best_versions_and_commits
    ]


async def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0])
    parser.add_argument(
        'cpython_dir', metavar='CPYTHON_DIR',
        help='directory with CPython source checkout')
    parser.add_argument(
        '--cache_dir',
        type=Path,
        default=Path('.cache'),
        help='Cache directory (large).')
    parser.add_argument(
        '--case_dir',
        type=Path,
        default=Path(__file__, '../cases'),
        help='Directory of cases.')

    args = parser.parse_args(argv[1:])
    root = Root.from_args(args)

    commits = (await get_latest_branch_releases(root))[-6:]
    report = Report(root, commits=commits)

    exceptions = []
    for run in await report.get_runs():
        result = await run.get_result()
        print(run, result, run.exception)
        if run.exception and not isinstance(run.exception, SkipBuild):
            exceptions.append(run.exception)
    if exceptions:
        raise ExceptionGroup('Runs failed', exceptions)

    print('ok')
