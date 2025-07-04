from pathlib import Path
import argparse
import asyncio
import sys

from .root import Root
from .report import Report
from .errors import SkipBuild


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

    report = Report(root)

    async with asyncio.TaskGroup() as tg:
        tasks = []
        for run in await report.get_runs():
            tasks.append((run, tg.create_task(run.get_result())))
        exceptions = []
        for run, task in tasks:
            result = await task
            print(run, result, run.exception)
            if run.exception and not isinstance(run.exception, SkipBuild):
                exceptions.append(run.exception)
        if exceptions:
            raise ExceptionGroup('Runs failed', exceptions)

    compile_builds = await report.get_compile_builds()
    size = max(len(str(b)) for b in compile_builds)
    for case in (await report.get_cases()):
        print(case)
        for compile_build in compile_builds:
            print(f'{compile_build!s:>{size}}', end=':')
            for exec_build in (await report.get_exec_builds()):
                run = report.get_run(case, compile_build, exec_build)
                result = await run.get_result()
                print(result.emoji, end='')
            print()

    print('ok')
