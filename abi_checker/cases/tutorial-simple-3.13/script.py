import extension

import sys

print(sys.version_info)

try:
    raise extension.SpamError
except extension.SpamError:
    pass
