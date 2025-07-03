import sys

print(sys.version_info)

import extension

try:
    raise extension.SpamError
except extension.SpamError:
    pass
