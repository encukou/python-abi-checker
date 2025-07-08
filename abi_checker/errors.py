class SkipBuild(Exception):
    """This build should be skipped"""

class ExpectFailure(Exception):
    """This build has an expected failure"""
