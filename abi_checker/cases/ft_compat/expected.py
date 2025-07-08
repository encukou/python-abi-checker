if not is_limited_api:
    raise ExpectFailure('needs limited API')

if limited_api < v(3, 5):
    raise ExpectFailure('needs limited API 3.5 for PyModuleDef_Init')
