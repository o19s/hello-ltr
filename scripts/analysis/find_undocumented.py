#!/usr/bin/env python3
"""Find undocumented functions, classes, and methods in Python files.

This script uses AST parsing to identify functions, classes, and methods
that lack docstrings, helping maintain code documentation standards.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Optional


class DocstringChecker(ast.NodeVisitor):
    """AST visitor that checks for missing docstrings in code definitions."""

    def __init__(self, filename: str):
        """Initialize the checker.

        Args:
            filename: Path to the file being checked.
        """
        self.filename = filename
        self.undocumented: list[tuple[str, str, int]] = []  # (type, name, line)
        self.current_class: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Visit a function definition.

        Args:
            node: AST node representing a function definition.
        """
        # Skip if it's a private method starting with __ (except special methods)
        is_private = node.name.startswith("__") and not (
            node.name.startswith("__") and node.name.endswith("__")
        )

        # Check for docstring
        has_docstring = ast.get_docstring(node) is not None or (
            len(node.body) > 0
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        if not has_docstring and not is_private:
            context = f"{self.current_class}." if self.current_class else ""
            self.undocumented.append(("function", f"{context}{node.name}", node.lineno))

        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Visit an async function definition.

        Args:
            node: AST node representing an async function definition.
        """
        # Skip if it's a private method starting with __ (except special methods)
        is_private = node.name.startswith("__") and not (
            node.name.startswith("__") and node.name.endswith("__")
        )

        # Check for docstring
        has_docstring = ast.get_docstring(node) is not None or (
            len(node.body) > 0
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        if not has_docstring and not is_private:
            context = f"{self.current_class}." if self.current_class else ""
            self.undocumented.append(("function", f"{context}{node.name}", node.lineno))

        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        """Visit a class definition.

        Args:
            node: AST node representing a class definition.
        """
        # Check for docstring
        has_docstring = ast.get_docstring(node) is not None or (
            len(node.body) > 0
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        if not has_docstring:
            self.undocumented.append(("class", node.name, node.lineno))

        # Set current class context for nested methods
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class


def check_file(filepath: Path) -> list[tuple[str, str, int]]:
    """Check a single Python file for undocumented definitions.

    Args:
        filepath: Path to the Python file to check.

    Returns:
        List of tuples (type, name, line_number) for undocumented items.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=str(filepath))
        checker = DocstringChecker(str(filepath))
        checker.visit(tree)
        return checker.undocumented
    except SyntaxError as e:
        print(f"Warning: Syntax error in {filepath}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return []


def find_python_files(
    root: Path,
    exclude_dirs: Optional[set[str]] = None,
    exclude_patterns: Optional[set[str]] = None,
) -> list[Path]:
    """Find all Python files in the directory tree.

    Args:
        root: Root directory to search.
        exclude_dirs: Set of directory names to exclude (e.g., {'__pycache__', '.git'}).
        exclude_patterns: Set of filename patterns to exclude.

    Returns:
        List of Path objects for Python files found.
    """
    if exclude_dirs is None:
        exclude_dirs = {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "env",
            ".env",
            "node_modules",
            ".pytest_cache",
            "htmlcov",
            ".mypy_cache",
            ".ruff_cache",
            "hello_ltr.egg-info",
        }
    if exclude_patterns is None:
        exclude_patterns = set()

    python_files = []
    for path in root.rglob("*.py"):
        # Skip if in excluded directory
        if any(excluded in path.parts for excluded in exclude_dirs):
            continue
        # Skip if matches exclude pattern
        if any(pattern in path.name for pattern in exclude_patterns):
            continue
        python_files.append(path)

    return sorted(python_files)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Find undocumented functions, classes, and methods in Python files."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to search (default: current directory)",
    )
    parser.add_argument(
        "--exclude-tests",
        action="store_true",
        help="Exclude test files from checking",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private methods (starting with _) in the check",
    )
    parser.add_argument(
        "--format",
        choices=["simple", "detailed", "json"],
        default="detailed",
        help="Output format (default: detailed)",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: Root directory '{root}' does not exist", file=sys.stderr)
        return 1

    exclude_patterns = set()
    if args.exclude_tests:
        exclude_patterns.add("test_")
        exclude_patterns.add("_test.py")

    python_files = find_python_files(root, exclude_patterns=exclude_patterns)

    all_undocumented = {}
    total_files = 0
    files_with_issues = 0

    for filepath in python_files:
        undocumented = check_file(filepath)
        total_files += 1
        if undocumented:
            files_with_issues += 1
            rel_path = filepath.relative_to(root)
            all_undocumented[str(rel_path)] = undocumented

    # Output results
    if args.format == "json":
        import json

        output = {
            "total_files": total_files,
            "files_with_issues": files_with_issues,
            "undocumented": {
                filepath: [
                    {"type": item_type, "name": name, "line": line}
                    for item_type, name, line in items
                ]
                for filepath, items in all_undocumented.items()
            },
        }
        print(json.dumps(output, indent=2))
    elif args.format == "simple":
        for filepath, items in sorted(all_undocumented.items()):
            for item_type, name, line in items:
                print(f"{filepath}:{line}: {item_type} '{name}'")
    else:  # detailed
        if all_undocumented:
            print(
                f"\nFound undocumented items in {files_with_issues}/{total_files} files:\n"
            )
            print("=" * 80)
            for filepath, items in sorted(all_undocumented.items()):
                print(f"\n{filepath}:")
                print("-" * 80)
                for item_type, name, line in items:
                    print(f"  Line {line:4d}: {item_type:8s} {name}")
            print("\n" + "=" * 80)
            print(
                f"\nTotal: {sum(len(items) for items in all_undocumented.values())} undocumented items"
            )
            return 1
        else:
            print(f"✓ All {total_files} files are fully documented!")
            return 0

    return 1 if all_undocumented else 0


if __name__ == "__main__":
    exit(main())
