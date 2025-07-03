# python-abi-checker

A tool to check ABI compatibility of C extensions across CPython builds.


## CLI

```
python -m abi_checker
```


## Web app

The Web app uses Quart.

Set `CPYTHON_DIR` to a Python source checkout, then run:

```
quart run --reload 
```
