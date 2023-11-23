import importlib.util
import os.path
import tempfile
import types

import build
import _compiled__init__ as compiled_cli

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

def test_cli():
    test_file = os.path.join(tempfile.gettempdir(), "test_file.py")
    with open(test_file, "w") as file:
        file.write(TEST_SOURCE)

    # patch the replaceable modules by putting the values from `build.py`
    compiled_cli.REPLACEABLE_MODULES = build.SUPPORTED_LIBRARIES

    try:
        returncode = compiled_cli.cli([test_file])
        assert returncode == 0

        with open(test_file) as file:
            contents = file.read()

        assert contents == EXPECTED_SOURCE
    finally:
        os.remove(test_file)
