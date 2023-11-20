# compiled

Compiled variants of the Python standard library.

## What is this project exactly?

Pure Python modules in the standard library can be a speed bottleneck sometimes,
this package aims to provide "compiled" variants of the pure Python standard
library modules, which are somewhere between **2-4x faster** than the builtin ones.

## Installation

```bash
pip install compiled
```

✨ This will install the `pycompile` CLI script as well.

## Usage

Say your program `asd.py` looks like this:

```python
import tomllib
from difflib import get_close_matches

# ... rest of the code
```

You can use the bundled `pycompile` script to turn those imports into the
"compiled" variants:

```python
$ pycompile asd.py
✨ Rewrote asd.py with compiled imports.

$ cat asd.py
import compiled.tomllib as tomllib
from compiled.difflib import get_close_matches

# ... rest of the code
```

With a real world program using `tomllib` and `difflib`, we get the following
difference in speed:

| Program        | Pure Python time | `compiled` time | **Speedup %**    |
| -------------- | ---------------- | --------------- | ---------------- |
| [hashes.py][1] | 1.907 seconds    | 1.028 seconds   | **85.5% faster** |

[1]: ./compiled_examples/hashes.py

## Local Development / Testing

- Create and activate a virtual environment.
- Run `pip install mypy`, as mypy[c] is the only dependency.
- Scripts to test, build and package standard libraries are present in
  `build.py`:

  ```console
  $ ./build.py test tomllib
  .............
  ----------------------------------------------------------------------
  Ran 13 tests in 0.006s
  OK

  $ ./build.py mypy tomllib
  Success: no issues found in 4 source files

  $ ./build.py package
  [...]
  ✨Built ./build/dist/compiled-0.2.1-cp311-cp311-macosx_13_0_arm64.whl
  ```

- Run `pytest compiled_tests` to run tests.
