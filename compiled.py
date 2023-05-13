#!/usr/bin/env python3.11
import argparse
import contextlib
import os
import shutil
import subprocess
from typing import Literal


ROOT_DIR = os.path.normpath(os.path.dirname(__file__))
LIB_BASE_DIR = os.path.join(ROOT_DIR, "Lib")
TEST_BASE_DIR = os.path.join(ROOT_DIR, "Lib/test")
TMP_LIB_DIR = os.path.join("/tmp/pycompiled")


def run_test(test_file_or_folder: str) -> None:
    with contextlib.chdir(TMP_LIB_DIR):
        test_relative_path = f"compiled_tests/{test_file_or_folder}"
        file_command = ["python", "-m" "unittest", test_relative_path]
        folder_command = [
            "python",
            "-m" "unittest",
            "discover",
            "-s",
            test_relative_path,
        ]
        subprocess.run(
            folder_command if os.path.isdir(test_relative_path) else file_command
        )


def run_mypy(library_name: str) -> None:
    with contextlib.chdir(TMP_LIB_DIR):
        subprocess.run(["mypy", "--strict", library_name])


def run_mypyc(library_name: str) -> None:
    with contextlib.chdir(TMP_LIB_DIR):
        subprocess.run(["mypyc", library_name])


def delete_python_files_and_pycache(library_name: str) -> None:
    library_path = os.path.join(TMP_LIB_DIR, library_name)
    shutil.rmtree(os.path.join(library_path, "__pycache__"), ignore_errors=True)
    for file in os.listdir(library_path):
        if file.endswith(".py"):
            os.remove(os.path.join(library_path, file))


class CompiledNamespace:
    subcommand: Literal["test", "mypy", "mypyc", "test_compiled"]
    library: str


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

    args = parser.parse_args(namespace=CompiledNamespace)
    library_name = args.library

    library_path = os.path.join(LIB_BASE_DIR, library_name)
    if not os.path.isdir(library_path):
        print(f"Library path {library_path} doesn't exist")
        return 1

    try:
        tmp_library_path = os.path.join(TMP_LIB_DIR, library_name)
        shutil.copytree(library_path, tmp_library_path)

        if os.path.isfile(os.path.join(TEST_BASE_DIR, f"test_{library_name}.py")):
            os.makedirs(os.path.join(TMP_LIB_DIR, "compiled_tests"), exist_ok=True)

            test_file_or_folder = f"test_{library_name}.py"
            test_file_path = os.path.join(TEST_BASE_DIR, test_file_or_folder)
            tmp_test_path = os.path.join(
                TMP_LIB_DIR, "compiled_tests", test_file_or_folder
            )
            shutil.copyfile(test_file_path, tmp_test_path)

        elif os.path.isdir(os.path.join(TEST_BASE_DIR, f"test_{library_name}")):
            test_file_or_folder = f"test_{library_name}"
            test_dir_path = os.path.join(TEST_BASE_DIR, test_file_or_folder)
            tmp_test_path = os.path.join(
                TMP_LIB_DIR, "compiled_tests", test_file_or_folder
            )
            shutil.copytree(test_dir_path, tmp_test_path)

        else:
            print(
                f"Test path test_{library_name} or test_{library_name}.py doesn't exist"
            )
            return 1

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
            run_test(test_file_or_folder)
        elif args.subcommand == "mypy":
            run_mypy(library_name)
        elif args.subcommand == "mypyc":
            run_mypyc(library_name)
        elif args.subcommand == "test_compiled":
            run_mypyc(library_name)
            delete_python_files_and_pycache(library_name)
            run_test(test_file_or_folder)

    finally:
        shutil.rmtree(TMP_LIB_DIR)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
