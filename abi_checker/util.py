import asyncio


class cached_task:
    """Like cached_property, but async"""
    def __init__(self, func):
        self.func = func
        self.attrname = None

    def __set_name__(self, owner, name):
        if self.attrname is None:
            self.attrname = name
        assert name == self.attrname

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        assert self.attrname is not None
        cache = instance.__dict__
        try:
            return cache[self.attrname]
        except KeyError:
            task = asyncio.create_task(
                self.func(instance),
                name=f'{self.attrname}() of {instance!r}',
            )
        async def get_task():
            return await task
        get_task.task = task
        cache[self.attrname] = get_task
        return get_task
