#!/usr/bin/env python3.11
import argparse
import contextlib
import glob
import os
import shutil
import subprocess
import sys
from textwrap import dedent
from typing import Literal

ROOT_DIR = os.path.normpath(os.path.dirname(__file__))
LIB_BASE_DIR = os.path.join(ROOT_DIR, "Lib")
TEST_BASE_DIR = os.path.join(ROOT_DIR, "Lib/test")
TMP_LIB_DIR = "/tmp/pycompiled"

PACKAGE_VERSION = "0.2.0"
SUPPORTED_LIBRARIES = ["tomllib", "difflib"]


def run_test(test_path: str) -> int:
    test_relative_path = os.path.relpath(test_path, TMP_LIB_DIR)
    with contextlib.chdir(TMP_LIB_DIR):
        file_command = [sys.executable, "-m" "unittest", test_relative_path]
        folder_command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            test_relative_path,
        ]
        process = subprocess.run(
            folder_command if os.path.isdir(test_relative_path) else file_command
        )
        return process.returncode


def run_mypy(library_path: str) -> int:
    library_relative_path = os.path.relpath(library_path, LIB_BASE_DIR)
    with contextlib.chdir(TMP_LIB_DIR):
        process = subprocess.run(["mypy", "--strict", library_relative_path])
        return process.returncode


def run_mypyc(library_path: str) -> int:
    library_relative_path = os.path.relpath(library_path, LIB_BASE_DIR)
    with contextlib.chdir(TMP_LIB_DIR):
        process = subprocess.run(["mypyc", "--strict", library_relative_path])
        return process.returncode


def delete_python_files_and_pycache(library_path: str) -> None:
    """Deletes all `.py` files and `__pycache__`, leaving `.pyc` files behind."""
    if os.path.isfile(library_path):
        pycache_path = os.path.join(os.path.dirname(library_path), "__pycache__")
        os.remove(library_path)
    else:
        pycache_path = os.path.join(library_path, "__pycache__")
        for file in os.listdir(library_path):
            if file.endswith(".py"):
                os.remove(os.path.join(library_path, file))

    # delete pycache
    shutil.rmtree(pycache_path)


class CompiledNamespace:
    subcommand: Literal["test", "mypy", "mypyc", "test_compiled", "package"]
    library: str


def setup_library(library_name: str):
    library_path = os.path.join(LIB_BASE_DIR, library_name + ".py")
    if not os.path.isfile(library_path):
        library_dir_path = os.path.join(LIB_BASE_DIR, library_name)
        if not os.path.isdir(library_dir_path):
            print(
                f"Library {library_path} not found. "
                f"(Tried {library_path}, {library_dir_path})"
            )
            return 1

        library_path = library_dir_path

    if os.path.isfile(library_path):
        tmp_library_path = shutil.copy(library_path, TMP_LIB_DIR)
    else:
        tmp_library_path = os.path.join(TMP_LIB_DIR, library_name)
        shutil.copytree(library_path, tmp_library_path)

    if os.path.isfile(os.path.join(TEST_BASE_DIR, f"test_{library_name}.py")):
        os.makedirs(os.path.join(TMP_LIB_DIR, "compiled_tests"), exist_ok=True)

        test_file_or_folder = f"test_{library_name}.py"
        test_file_path = os.path.join(TEST_BASE_DIR, test_file_or_folder)
        tmp_test_path = os.path.join(TMP_LIB_DIR, "compiled_tests", test_file_or_folder)
        shutil.copyfile(test_file_path, tmp_test_path)

    elif os.path.isdir(os.path.join(TEST_BASE_DIR, f"test_{library_name}")):
        test_file_or_folder = f"test_{library_name}"
        test_dir_path = os.path.join(TEST_BASE_DIR, test_file_or_folder)
        tmp_test_path = os.path.join(TMP_LIB_DIR, "compiled_tests", test_file_or_folder)
        shutil.copytree(test_dir_path, tmp_test_path)

    else:
        print(f"Test path test_{library_name} or test_{library_name}.py doesn't exist")
        return 1

    return library_path, tmp_library_path, tmp_test_path


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    test_parser = subparsers.add_parser("test")
    test_parser.add_argument("library")

    mypy_parser = subparsers.add_parser("mypy")
    mypy_parser.add_argument("library")

    mypyc_parser = subparsers.add_parser("mypyc")
    mypyc_parser.add_argument("library")

    test_compiled_parser = subparsers.add_parser("test_compiled")
    test_compiled_parser.add_argument("library")

    # This subcommand won't be for a specific library.
    subparsers.add_parser("package")

    args = parser.parse_args(namespace=CompiledNamespace)

    if os.path.exists(TMP_LIB_DIR):
        shutil.rmtree(TMP_LIB_DIR)

    os.makedirs(TMP_LIB_DIR)

    if args.subcommand == "package":
        for library_name in SUPPORTED_LIBRARIES:
            library_path, tmp_library_path, _ = setup_library(library_name)
            returncode = run_mypyc(library_path)
            if returncode != 0:
                return returncode

            delete_python_files_and_pycache(tmp_library_path)

        # if we reached this far, we can just collect all *.so files and move them to
        # ./build/compiled, and then run setuptools in root dir.
        # but only after deleting build artifacts.
        shutil.rmtree(os.path.join(TMP_LIB_DIR, "build"))
        shared_objects = glob.glob("**/*.so", recursive=True, root_dir=TMP_LIB_DIR)

        build_dir = os.path.abspath("./build")
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

        compiled_src_path = os.path.join(build_dir, "compiled")
        os.makedirs(compiled_src_path)

        with contextlib.chdir(TMP_LIB_DIR):
            for shared_object in shared_objects:
                dest_path = os.path.join(compiled_src_path, shared_object)
                dest_folder = os.path.dirname(dest_path)
                os.makedirs(dest_folder, exist_ok=True)
                shutil.copy(shared_object, dest_path)

        # Add the `__init__.py` with console script to package
        with open("./_compiled__init__.py") as init_file:
            contents = init_file.read()

        # Populate the supported libraries in the init file
        contents = contents.replace(
            "REPLACEABLE_MODULES = []", f"REPLACEABLE_MODULES = {SUPPORTED_LIBRARIES!r}"
        )
        with open(os.path.join(compiled_src_path, "__init__.py"), "w") as init_file:
            init_file.write(contents)

        # setup.py contains the `pycompile` console script, present in `__init__.py`
        with contextlib.chdir(build_dir):
            setup_code = dedent(
                # TODO: use a setup.cfg for README, version, and all the static stuff.
                r"""
                from setuptools import setup

                setup(
                    name="compiled",
                    version=%r,
                    description="Compiled versions of the stdlib.",
                    long_description="# compiled\n\nCompiled versions of the stdlib.",
                    url="https://github.com/tusharsadhwani/astest",
                    author="Tushar Sadhwani",
                    author_email="tushar.sadhwani000@gmail.com",
                    packages=["compiled"],
                    package_data={"compiled": %r},
                    entry_points={
                        "console_scripts": ["pycompile=compiled:cli"],
                    },
                )
                """
                % (PACKAGE_VERSION, shared_objects,)
            )
            with open("./setup.py", "w") as setup_file:
                setup_file.write(setup_code)

            process = subprocess.run(["python", "setup.py", "sdist", "bdist_wheel"])
            return process.returncode

    library_name = args.library
    library_path, tmp_library_path, tmp_test_path = setup_library(library_name)

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

    if args.subcommand == "test":
        return run_test(tmp_test_path)

    if args.subcommand == "mypy":
        return run_mypy(library_path)

    if args.subcommand == "mypyc":
        return run_mypyc(library_path)

    if args.subcommand == "test_compiled":
        returncode = run_mypyc(library_path)
        if returncode != 0:
            return returncode

        delete_python_files_and_pycache(tmp_library_path)
        return run_test(tmp_test_path)

    raise AssertionError("unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(TMP_LIB_DIR, ignore_errors=True)
