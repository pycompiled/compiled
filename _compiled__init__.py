"""
Console script for the `compiled` package.

This is modified by `./build.py` before creating the package.
Not to be run directly.
"""
from __future__ import annotations

import argparse
import ast
import glob
import os


# To be populated by `./build.py`
REPLACEABLE_MODULES: list[str] = []


class PyCompiledArgs:
    path: str
    ignore_errors: bool


Import = ast.Import | ast.ImportFrom


def error(string: str) -> None:
    """Print an error."""
    print(f"\033[31;1mERROR: {string}\033[m")


def warning(string: str) -> None:
    """Print a warning."""
    print(f"\033[32;1mWARNING: {string}\033[m")


def get_compileable_imports(tree: ast.Module) -> tuple[list[Import], list[Import]]:
    """
    Finds all imports that can use the `compiled` module, and returns them
    as well as their replacement "compiled" imports.
    """
    original_imports: list[Import] = []
    replacement_imports: list[Import] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        new_node: Import
        new_aliases: list[ast.alias] = []
        if isinstance(node, ast.Import):
            if all(alias.name not in REPLACEABLE_MODULES for alias in node.names):
                # No need to change this import
                continue

            for alias in node.names:
                alias_name = alias.name
                if alias_name not in REPLACEABLE_MODULES:
                    new_aliases.append(alias)
                    continue

                asname = alias.asname if alias.asname is not None else alias.name
                new_alias = ast.alias(name=f"compiled.{alias_name}", asname=asname)
                new_aliases.append(new_alias)

            new_node = ast.Import(names=new_aliases)
            original_imports.append(node)
            replacement_imports.append(new_node)

        else:
            # FromImport simply needs to change the module name
            if node.module not in REPLACEABLE_MODULES:
                continue

            new_node = ast.ImportFrom(
                module=f"compiled.{node.module}",
                names=node.names,
                level=node.level,
            )
            original_imports.append(node)
            replacement_imports.append(new_node)

    return original_imports, replacement_imports


def replace_import(
    sourcelines: list[bytes],
    original_import: Import,
    replacement_import: Import,
) -> None:
    """
    Replaces the original with the replacement import in the sourcelines.

    Works by:
    - Finding the range of lines that contain the given import.
    - Replacing the first line with our import line while preserving whitespace.
      (we only produce single line imports)
    - Splicing the last line to preserve any end comments and appending that to the
      import line.
    - All middle lines of the import are discarded.
    """
    replacement_import_bytes = ast.unparse(replacement_import).encode()

    start_lineno, start_offset = original_import.lineno, original_import.col_offset
    end_lineno, end_offset = original_import.end_lineno, original_import.end_col_offset
    assert end_lineno is not None

    # make the line numbers zero indexed to match sourcelines
    start_lineno -= 1
    end_lineno -= 1

    # Preserve prefix, i.e. import's leading whitespace
    start_line = sourcelines[start_lineno]
    start_prefix = start_line[:start_offset]
    replacement_import_bytes = start_prefix + replacement_import_bytes

    # Preserve suffix, i.e. trailing comments and stuff at the end of the import
    end_line = sourcelines[end_lineno]
    end_suffix = end_line[end_offset:]
    replacement_import_bytes += end_suffix

    sourcelines[start_lineno] = replacement_import_bytes

    # remove middle lines as well as end line
    del sourcelines[start_lineno + 1 : end_lineno + 1]


def cli(argv: list[str] | None = None) -> int:
    """CLI interface."""
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Python file or package to use compiled stdlib in")
    parser.add_argument("--ignore-errors", action="store_true")
    args = parser.parse_args(argv, namespace=PyCompiledArgs)
    if not os.path.exists(args.path):
        error(f"file not found: {args.path}")
        return 1

    if os.path.isdir(args.path):
        python_files = glob.glob("**/*.py", recursive=True, root_dir=args.path)
    else:
        python_files = [args.path]

    for python_file in python_files:
        with open(python_file, "rb") as file:
            source = file.read()

        try:
            tree = ast.parse(source)
        except (ValueError, SyntaxError):
            if args.ignore_errors:
                warning(f"failed to parse {python_file}, skipping...")
                continue
            else:
                error(
                    f"failed to parse {python_file}.\n"
                    "To ignore parse errors, use the `--ignore-errors` flag."
                )
                return 2

        original_imports, replacement_imports = get_compileable_imports(tree)
        # Reverse them so that we can safely edit the source code going backwards
        original_imports = original_imports[::-1]
        replacement_imports = replacement_imports[::-1]

        sourcelines = source.splitlines(keepends=True)
        for original_import, replacement_import in zip(
            original_imports, replacement_imports, strict=True
        ):
            replace_import(sourcelines, original_import, replacement_import)

        new_source = b"".join(sourcelines)
        with open(python_file, "wb") as file:
            file.write(new_source)

        print(f"✨ Rewrote {python_file} with compiled imports.")

    return 0
