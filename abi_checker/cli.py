from pathlib import Path
import argparse
import asyncio
import sys

from .root import Root
from .report import Report
from .runresult import RunResult


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
        tg.create_task(write_report(report))

        tasks = []
        for run in await report.get_runs():
            async def task(run):
                return run, await run.get_result()
            tasks.append(tg.create_task(task(run)))

        exceptions = []
        async for task in asyncio.as_completed(tasks):
            run, result = await task
            print(run, result, run.exception)
            if result == RunResult.ERROR:
                exceptions.append(run.exception)
        if exceptions:
            raise ExceptionGroup('Runs failed', exceptions)

    await write_report(report)

    print('ok')

async def write_report(report):
    compile_builds = list(await report.get_compile_builds())
    build_size = max(len(str(b)) for b in compile_builds)
    opt_size = max(
            len(str(comp_opts))
            for comp_opts in (await report.get_possible_compile_options())
    )
    for case in (await report.get_cases()):
        print(case)
        for compile_build in compile_builds:
            build_header = f'{compile_build!s:>{build_size}}'
            for comp_opts in (await compile_build.get_possible_compile_options()):
                parts = []
                parts.append(f'{build_header}:{comp_opts!s:>{opt_size}}:')
                for exec_build in (await report.get_exec_builds()):
                    run = report.get_run(
                        case, compile_build, comp_opts, exec_build)
                    result = await run.get_result()
                    parts.append(result.emoji)
                print(''.join(parts))
            build_header = ' ' * len(build_header)
