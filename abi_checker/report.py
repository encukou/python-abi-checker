from functools import cached_property
import asyncio

from .case import Cases
from .build import Build
from .errors import SkipBuild
from .caserun import CaseRun
from .feature import _FEATURES

class Report:
    def __init__(self, root, *, commits, builds=None):
        self.root = root
        self.commits = commits
        self._builds = builds
        self._cases = None
        self._runs = None
        self._rundict = {}

    async def get_builds(self):
        async with self.lock:
            if self._builds is not None:
                return self._builds
            self._builds = []
            async with asyncio.TaskGroup() as tg:
                for commit in self.commits:
                    for feature in (None, *_FEATURES.values()):
                        features = (feature,) if feature else ()
                        tg.create_task(_add_build(
                            self._builds, self.root, commit, features,
                        ))
        return self._builds

    async def get_cases(self):
        async with self.lock:
            if self._cases is not None:
                return self._cases
            cases = Cases(self.root)
            self._cases = list(cases.values())
        return self._cases

    async def get_runs(self):
        if self._runs is not None:
            return self._runs
        builds = await self.get_builds()
        cases = await self.get_cases()
        async with self.lock:
            if self._runs is not None:
                return self._runs
            self._runs = []
            async with asyncio.TaskGroup() as tg:
                for comp_build in builds:
                    for run_build in builds:
                        for case in cases:
                            run = self.get_run(
                                case, comp_build, run_build)
                            self._runs.append(run)
                            tg.create_task(run.get_result())
        return self._runs

    def get_run(self, *args):
        try:
            return self._rundict[args]
        except KeyError:
            run = CaseRun(*args)
            self._rundict[args] = run
            return run

    @cached_property
    def lock(self):
        return asyncio.Lock()


async def _add_build(result, root, commit, features):
    for feature in features:
        try:
            await feature.verify_compatibility(commit)
        except SkipBuild:
            return
    result.append(Build(root, commit, features))
