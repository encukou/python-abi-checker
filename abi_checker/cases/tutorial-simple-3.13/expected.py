
if compile_version < v(3, 10):
    raise ExpectFailure('needs 3.10 for PyModule_AddObjectRef')

if exec_version < v(3, 10):
    raise ExpectFailure('needs 3.10 for PyModule_AddObjectRef')

if is_limited_api and limited_api < v(3, 10):
    if v(3, 10) < compile_version < v(3, 11):
        # https://github.com/python/cpython/issues/107226
        pass
    else:
        raise ExpectFailure('needs 3.10 for PyModule_AddObjectRef')

if ('t' in compile_features) ^ ('t' in exec_features):
    raise ExpectFailure('gil/free-threading must match')
