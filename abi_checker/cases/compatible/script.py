import extension

values = [
    extension.increment_value(),
    extension.increment_value(),
    extension.increment_value(),
    extension.increment_value(),
]
print(values)
assert values == [0, 1, 2, 3]
