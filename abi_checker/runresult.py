import enum


class RunResult(enum.Enum):
    SUCCESS = 'success', '✅'
    BUILD_FAILURE = 'build failure', '⛔'
    EXEC_FAILURE = 'exec failure', '❌'
    SKIPPED = 'skipped', '❔'
    EXPECTED_FAILURE = 'expected failure', '➖'
    UNEXPECTED_SUCCESS = 'unexpected success', '🎆'
    ERROR = 'error', '💥'

    def __new__(cls, value, emoji):
        self = object.__new__(cls)
        self._value_ = value
        self.emoji = emoji
        return self
