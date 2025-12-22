#!/usr/bin/env python3
"""
Script to analyze which dependencies in pyproject.toml are actually used in the codebase.

Usage:
    python3 analyze_dependencies.py
"""

import os
import re
from collections import defaultdict
from pathlib import Path

# Try to import TOML parser (tomllib in Python 3.11+, tomli for older versions)
try:
    import tomllib  # type: ignore[import-untyped] # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import-untyped] # Fallback for older Python versions
    except ImportError:
        raise ImportError(
            "TOML parser not found. Install tomli: pip install tomli"
        ) from None

# Read pyproject.toml
# Script is in scripts/analysis/, so go up two levels to project root
project_root = Path(__file__).parent.parent.parent
pyproject_file = project_root / "pyproject.toml"

if not pyproject_file.exists():
    raise FileNotFoundError(f"pyproject.toml not found at {pyproject_file}")

with open(pyproject_file, "rb") as f:
    pyproject_data = tomllib.load(f)

# Extract dependencies from [project.dependencies]
dependencies = {}
if "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
    for dep_line in pyproject_data["project"]["dependencies"]:
        # Parse package name (handle version specifiers)
        # Remove comments if present
        dep_line = dep_line.split("#")[0].strip()
        if not dep_line:
            continue
        parts = re.split(r"[<>=!]+", dep_line)
        pkg_name = parts[0].strip().lower()
        dependencies[pkg_name] = dep_line
else:
    raise ValueError("No [project.dependencies] section found in pyproject.toml")

# Map package names to import names (some packages have different import names)
IMPORT_MAP = {
    "opensearch-py": "opensearchpy",
    "scikit-learn": "sklearn",
    "ipython-genutils": "IPython",
    "python-dateutil": "dateutil",
    "send2trash": "Send2Trash",
    "widgetsnbextension": None,  # No direct import
    "jinja2": "jinja2",
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "scipy": "scipy",
    "plotly": "plotly",
    "plotnine": "plotnine",
    "mizani": "mizani",
    "fuzzywuzzy": "fuzzywuzzy",
    "retrying": "retrying",
    "nbformat": "nbformat",
    "nbconvert": "nbconvert",
    "joblib": "joblib",
    "xgboost": "xgboost",
    "cython": "cython",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
}

# Find all Python files
python_files = []
for root, dirs, files in os.walk("."):
    # Skip hidden directories and common ignore patterns
    dirs[:] = [
        d
        for d in dirs
        if not d.startswith(".") and d not in ["__pycache__", "node_modules"]
    ]
    for file in files:
        if file.endswith(".py"):
            python_files.append(os.path.join(root, file))

# Find all notebook files
notebook_files = []
for root, dirs, files in os.walk("."):
    dirs[:] = [
        d
        for d in dirs
        if not d.startswith(".") and d not in ["__pycache__", "node_modules"]
    ]
    for file in files:
        if file.endswith(".ipynb"):
            notebook_files.append(os.path.join(root, file))

# Track usage
used_packages = defaultdict(list)


def check_package_in_content(pkg_name, import_name, content):
    """Check if a specific package is imported in content."""
    if import_name is None:
        return False

    # Check import statements (more precise)
    import_patterns = [
        rf"\bimport\s+{re.escape(import_name)}\b",
        rf"\bfrom\s+{re.escape(import_name)}\s+import",
        rf"\bfrom\s+{re.escape(import_name)}\.",  # from package.submodule
    ]

    # For notebooks, also check in code cells
    for pattern in import_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    # Special case: check for common aliases
    aliases = {
        "pandas": "pd",
        "numpy": "np",
        "matplotlib": ["plt", "matplotlib"],
        "sklearn": "sklearn",
        "scikit-learn": "sklearn",
        "plotly": "plotly",
        "plotnine": "p9",
        "seaborn": "sns",
        "scipy": "scipy",
    }

    if pkg_name in aliases:
        alias = aliases[pkg_name]
        if isinstance(alias, list):
            for a in alias:
                if re.search(rf"\b{re.escape(a)}\b", content, re.IGNORECASE):
                    return True
        else:
            if re.search(rf"\b{re.escape(alias)}\b", content, re.IGNORECASE):
                return True

    return False


# Check all files for each package (exclude this script)
all_files = python_files + notebook_files
script_name = os.path.basename(__file__)
all_files = [f for f in all_files if script_name not in f]

for pkg_name, _req_line in dependencies.items():
    import_name = IMPORT_MAP.get(pkg_name, pkg_name)

    for filepath in all_files:
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if check_package_in_content(pkg_name, import_name, content):
                    used_packages[pkg_name].append(filepath)
        except Exception:
            pass  # Skip files that can't be read

# Special cases - check for indirect usage
# Check Dockerfile for graphviz
dockerfile_path = project_root / "Dockerfile"
if dockerfile_path.exists():
    with open(dockerfile_path) as f:
        if "graphviz" in f.read().lower():
            used_packages["graphviz"].append("Dockerfile")

# Categorize dependencies
used = set(used_packages.keys())
all_deps = set(dependencies.keys())
unused = all_deps - used

# Print results
print("=" * 80)
print("DEPENDENCY USAGE ANALYSIS")
print("=" * 80)
print(f"\nTotal dependencies: {len(all_deps)}")
print(f"Used dependencies: {len(used)}")
print(f"Potentially unused dependencies: {len(unused)}")
print("\n" + "=" * 80)
print("\nUSED DEPENDENCIES:")
print("=" * 80)
for pkg in sorted(used):
    files = used_packages[pkg]
    print(f"\n{pkg} ({dependencies[pkg]})")
    print(f"  Found in {len(files)} file(s):")
    for f in files[:5]:  # Show first 5 files
        print(f"    - {f}")
    if len(files) > 5:
        print(f"    ... and {len(files) - 5} more")

print("\n" + "=" * 80)
print("\nPOTENTIALLY UNUSED DEPENDENCIES:")
print("=" * 80)
print("\nNote: These may be:")
print("  - Transitive dependencies (required by other packages)")
print("  - Used indirectly or dynamically")
print("  - Required for Jupyter notebook infrastructure")
print("  - Used in notebooks but not detected")
print()

for pkg in sorted(unused):
    print(f"  {pkg} ({dependencies[pkg]})")

print("\n" + "=" * 80)
print("\nNOTES:")
print("=" * 80)
print("""
- Jupyter/IPython packages (ipykernel, ipython, jupyter, notebook, etc.) are likely
  needed for notebook functionality even if not directly imported in Python code.

- Many packages listed as 'unused' may be transitive dependencies required by
  packages that ARE used (e.g., certifi, chardet, idna, urllib3 are dependencies
  of requests).

- Some packages like 'graphviz' may be used via system commands rather than
  Python imports.

- Notebooks may use packages that aren't detected by static analysis.

See DEPENDENCY_ANALYSIS.md for a detailed breakdown.
""")
