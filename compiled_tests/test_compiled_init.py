import importlib.util
import os.path
import tempfile
import types


TEST_SOURCE = r"""
import sys
from sys import argv
import difflib
import tomllib \
    as tomli  # preserve this comment

def foo():
    # these are unused
    from difflib import (
        ndiff,
        SequenceMatcher as SM,
        )  # another comment

    sm = SM()
    return ndiff("foo", "bar")

with open("foo.toml", "rb") as file:
    contents = tomli.load(file)

names = contents["names"]
for name in namees:
    matches = difflib.get_close_matches(name, names - {name}, n=1, cutoff=.9)
    if not matches:
        continue

    match = matches[0]
    print("Similar hashes:", hash, match)
"""

EXPECTED_SOURCE = r"""
import sys
from sys import argv
import compiled.difflib as difflib
import compiled.tomllib as tomli  # preserve this comment

def foo():
    # these are unused
    from compiled.difflib import ndiff, SequenceMatcher as SM  # another comment

    sm = SM()
    return ndiff("foo", "bar")

with open("foo.toml", "rb") as file:
    contents = tomli.load(file)

names = contents["names"]
for name in namees:
    matches = difflib.get_close_matches(name, names - {name}, n=1, cutoff=.9)
    if not matches:
        continue

    match = matches[0]
    print("Similar hashes:", hash, match)
"""


def import_from_root(filename: str) -> types.ModuleType:
    root_dir = os.path.dirname(os.path.dirname(__file__))
    module_path = os.path.join(root_dir, filename)
    spec = importlib.util.spec_from_file_location(filename, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli():
    test_file = os.path.join(tempfile.gettempdir(), "test_file.py")
    with open(test_file, "w") as file:
        file.write(TEST_SOURCE)

    # patch the replaceable modules by putting the values from `build.py`
    build = import_from_root("build.py")
    compiled_cli = import_from_root("_compiled__init__.py")
    compiled_cli.REPLACEABLE_MODULES = build.SUPPORTED_LIBRARIES

    try:
        returncode = compiled_cli.cli([test_file])
        assert returncode == 0

        with open(test_file) as file:
            contents = file.read()

        assert contents == EXPECTED_SOURCE
    finally:
        os.remove(test_file)
