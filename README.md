# python-abi-checker

A tool to check ABI compatibility of C extensions across CPython builds.

Tested on Linux; fixes for other platforms welcome.


## CLI

I recommend running the CLI first; it better shows what's going on
as the cache is filled.
Note that its will start many processes in parallel.

```
python -m abi_checker <path_to_Python_source_checkout>
```


## Web app

The Web app report is a bit easier to understand (though still very Spartan).

It uses Quart; install it first.

Set `CPYTHON_DIR` to a Python source checkout, then run:

```
quart run --reload 
```
