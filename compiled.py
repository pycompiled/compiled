#!/usr/bin/env python3.11
import argparse
import contextlib
import os
import shutil
import subprocess


ROOT_DIR = os.path.normpath(os.path.dirname(__file__))
LIB_BASE_DIR = os.path.join(ROOT_DIR, "Lib")
TEST_BASE_DIR = os.path.join(ROOT_DIR, "Lib/test")
TMP_LIB_DIR = os.path.join("/tmp/pycompiled")


def run_test(library_name) -> None:
    with contextlib.chdir(TMP_LIB_DIR):
        command = [
            "python",
            "-m" "unittest",
            "discover",
            "-s" f"compiled_tests/test_{library_name}",
        ]
        subprocess.run(command)


def _run_command(_) -> None:
    ...


def run_mypy() -> None:
    _run_command("mypy")


def run_mypyc() -> None:
    _run_command("mypyc")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    test_parser = subparsers.add_parser("test")
    test_parser.add_argument("library")

    mypy_parser = subparsers.add_parser("mypy")
    mypy_parser.add_argument("library")

    mypyc_parser = subparsers.add_parser("mypyc")
    mypyc_parser.add_argument("library")

    args = parser.parse_args()
    library_name = args.library

    library_path = os.path.join(LIB_BASE_DIR, library_name)
    if not os.path.isdir(library_path):
        print(f"Library path {library_path} doesn't exist")
        return 1
    tmp_library_path = os.path.join(TMP_LIB_DIR, library_name)

    tests_path = os.path.join(TEST_BASE_DIR, f"test_{library_name}")
    if not os.path.isdir(tests_path):
        print(f"Test path {tests_path} doesn't exist")
        return 1
    tmp_test_path = os.path.join(TMP_LIB_DIR, "compiled_tests", f"test_{library_name}")

    shutil.copytree(library_path, tmp_library_path)
    shutil.copytree(tests_path, tmp_test_path)

    # Special case: tomllib does `from . import tomllib` for some reason.
    # Change that to `import tomllib` in tests.
    if library_name == "tomllib":
        for filename in os.listdir(tmp_test_path):
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(tmp_test_path, filename)
            with open(filepath) as f:
                contents = f.read()

            with open(filepath, "w") as f:
                f.write(contents.replace("from . import", "import"))

    try:
        if args.subcommand == "test":
            run_test(library_name)
        elif args.subcommand == "mypy":
            run_mypy()
        elif args.subcommand == "mypyc":
            run_mypyc()

    finally:
        shutil.rmtree(tmp_library_path)
        shutil.rmtree(tmp_test_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
