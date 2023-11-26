#!/usr/bin/env python3.11
import argparse
import ast
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

SUPPORTED_LIBRARIES = ["tomllib", "difflib"]

# get rid of this once mypyc fixes relative imports
from _compiled__init__ import replace_import


def rewrite_relative_imports(path: str, package_name: str) -> None:
    """
    Find all `from .foo import bar` imports and makeit absolute.
    This is done because mypyc seems to break on relative imports.
    """
    if os.path.isdir(path):
        python_files = glob.glob(f"{glob.escape(path)}/**/*.py", recursive=True)
    else:
        python_files = [path]

    for python_file in python_files:
        import_replacements: list[tuple[ast.ImportFrom], tuple[ast.ImportFrom]] = []
        with open(python_file, "rb") as file:
            source = file.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue

            if node.level == 0:
                continue

            if node.level > 1:
                raise NotImplementedError(f"Unsupported import level: {node.level}")

            # Relative import found, create compiled.<pkgname> import
            absolure_module_name = (
                f"compiled.{package_name}"
                if node.module is None
                else f"compiled.{package_name}.{node.module}"
            )
            replaement_node = ast.ImportFrom(
                module=absolure_module_name,
                names=node.names,
                level=0,
            )
            import_replacements.append((node, replaement_node))

        # Reverse them so that we can safely edit the source code going backwards
        import_replacements = import_replacements[::-1]

        sourcelines = source.splitlines(keepends=True)
        for original_import, replacement_import in import_replacements:
            replace_import(sourcelines, original_import, replacement_import)

        new_source = b"".join(sourcelines)
        with open(python_file, "wb") as file:
            file.write(new_source)

        print(f"NOTE: Rewrote {python_file} with absolute imports.")


def run_test(test_path: str) -> int:
    test_relative_path = os.path.relpath(test_path, TMP_LIB_DIR)
    with contextlib.chdir(TMP_LIB_DIR):
        file_command = [sys.executable, "-m", "unittest", test_relative_path]
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


def get_library_path(library_name: str) -> str:
    library_path = os.path.join(LIB_BASE_DIR, library_name + ".py")
    if not os.path.isfile(library_path):
        library_dir_path = os.path.join(LIB_BASE_DIR, library_name)
        if not os.path.isdir(library_dir_path):
            raise FileNotFoundError(
                f"Library {library_path} not found. "
                f"(Tried {library_path}, {library_dir_path})"
            )

        library_path = library_dir_path

    return library_path


def setup_library(library_name: str):
    try:
        library_path = get_library_path(library_name)
    except FileNotFoundError as exc:
        err_msg = exc.args[0]
        print(f"Error in setting up {library_name}:", err_msg)
        return 1

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
        build_dir = os.path.abspath("./build")
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

        compiled_src_path = os.path.join(build_dir, "compiled")
        os.makedirs(compiled_src_path)

        for library_name in SUPPORTED_LIBRARIES:
            library_path = get_library_path(library_name)
            if os.path.isfile(library_path):
                shutil.copy(library_path, compiled_src_path)
            else:
                library_folder = os.path.join(compiled_src_path, library_name)
                shutil.copytree(library_path, library_folder)

            # HACK: mypyc seems to not like relative imports in packages.
            # so for now, replace relative imports with absolute ones.
            rewrite_relative_imports(library_folder, library_name)

        # Gets all relative paths to `setup.py`, i.e. `tomllib/__init__.py` etc.
        ext_modules = glob.glob("**/*.py", recursive=True, root_dir=build_dir)

        # Add the `__init__.py` with console script to package
        with open("./_compiled__init__.py") as init_file:
            contents = init_file.read()

        # Populate the supported libraries in the init file
        contents = contents.replace(
            "REPLACEABLE_MODULES: list[str] = []",
            f"REPLACEABLE_MODULES: list[str] = {SUPPORTED_LIBRARIES!r}",
        )
        with open(os.path.join(compiled_src_path, "__init__.py"), "w") as init_file:
            init_file.write(contents)

        # copy README.md to build dir
        shutil.copy("./README.md", build_dir)

        # copy cibuildwheel config to build dir
        pyproject_toml_path = os.path.join(build_dir, "pyproject.toml")
        shutil.copy("./_compiled_pyproject.toml", pyproject_toml_path)

        # setup.py contains the `pycompile` console script, present in `__init__.py`
        with contextlib.chdir(build_dir):
            setup_code = dedent(
                r"""
                from setuptools import setup, find_packages

                from mypyc.build import mypycify

                setup(
                    packages=find_packages(),
                    ext_modules=mypycify(["--strict", *%r]),
                    entry_points={
                        "console_scripts": ["pycompile=compiled:cli"],
                    },
                )
                """
                % (ext_modules,)
            )
            with open("./setup.py", "w") as setup_file:
                setup_file.write(setup_code)

            if os.getenv('GITHUB_ACTIONS') == 'true':
                # Running in CI, use cibuildwheel
                process = subprocess.run(["cibuildwheel"])
            else:
                # Running locally, build a regular bdist_wheel
                process = subprocess.run(["python", "setup.py", "bdist_wheel"])

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
