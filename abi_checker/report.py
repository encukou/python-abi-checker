from functools import cached_property
import collections
import asyncio

from .case import Cases
from .build import Build
from .errors import SkipBuild
from .commit import get_tagged_commits
from .caserun import CaseRun
from .feature import _FEATURES
from .pyversion import PyVersion

class Report:
    def __init__(self, root, *, commits=None, builds=None):
        self.root = root
        self._commits = commits
        self._builds = builds
        self._cases = None
        self._runs = None
        self._rundict = {}

    async def get_commits(self):
        async with self.lock:
            if self._commits is not None:
                return self._commits
            self._commits = (await get_latest_branch_releases(self.root))[-6:]
        return self._commits

    async def get_builds(self):
        if self._builds is not None:
            return self._builds
        commits = await self.get_commits()
        async with self.lock:
            if self._builds is not None:
                return self._builds
            self._builds = []
            tasks = []
            async with asyncio.TaskGroup() as tg:
                for commit in commits:
                    for feature in (None, *_FEATURES.values()):
                        features = (feature,) if feature else ()
                        tasks.append(tg.create_task(_make_build(
                            self._builds, self.root, commit, features,
                        )))
            self._builds = [(await t) for t in tasks if (await t)]
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


async def _make_build(result, root, commit, features):
    for feature in features:
        try:
            await feature.verify_compatibility(commit)
        except SkipBuild:
            return None
    return Build(root, commit, features)


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
