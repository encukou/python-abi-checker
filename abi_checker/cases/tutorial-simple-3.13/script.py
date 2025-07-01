import extension

try:
    raise extension.SpamError
except extension.SpamError:
    pass
