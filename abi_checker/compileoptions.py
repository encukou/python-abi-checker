from functools import cached_property
import dataclasses

from .pyversion import PyVersion


@dataclasses.dataclass(frozen=True)
class CompileOptions:
    limited_api: int | None

    def __lt__(self, other):
        return self._sort_key < other._sort_key

    @cached_property
    def _sort_key(self):
        return self.limited_api is not None, self.limited_api

    @cached_property
    def tag(self):
        if self.limited_api is None:
            return '~'
        return format(self.limited_api, '08x')

    @cached_property
    def is_limited_api(self):
        return self.limited_api is not None

    @cached_property
    def limited_api_pyversion(self):
        if self.limited_api == 3:
            return PyVersion.pack(3, 2)
        if self.limited_api is not None:
            return PyVersion.from_hex(self.limited_api)

    @classmethod
    def parse(cls, source):
        if source == '~':
            return cls(None)
        return cls(int(source, 16))

    def __str__(self):
        if self.limited_api is None:
            return '~'
        if self.limited_api == 3:
            return '3'
        if (self.limited_api & 0xff00ffff) == 0x03000000:
            return f'3.{(self.limited_api >> 16) & 0xff}'
        return format(self.limited_api, '08x')

    @cached_property
    def cflags(self):
        if self.limited_api is None:
            return []
        if self.limited_api == 3:
            return ['-DPy_LIMITED_API=3']
        return [f'-DPy_LIMITED_API=0x{self.limited_api:08x}']
