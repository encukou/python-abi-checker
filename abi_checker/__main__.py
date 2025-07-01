import asyncio
import sys

from .cli import main

exit(asyncio.run(main(sys.argv)))
