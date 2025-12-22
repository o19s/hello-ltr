# Type Stubs Directory

This directory contains custom type stubs (`.pyi` files) for third-party libraries that don't have official type stub packages available.

## Current Stubs

- `plotnine-stubs/` - Type stubs for the plotnine library (ggplot2 for Python)
- `plotly-stubs/` - Type stubs for plotly library (interactive plotting)
- `pandas-stubs/` - Type stubs for pandas library (data analysis)
- `sklearn-stubs/` - Type stubs for scikit-learn library (machine learning)

**Note on pandas:** pandas 2.0+ includes built-in type annotations, but pyright may still report warnings in some cases. The custom stubs provide fallback type information to suppress these warnings.

**Note on sklearn:** scikit-learn 1.3.0+ includes built-in type annotations, but pyright may still report warnings in some cases. The custom stubs provide fallback type information to suppress these warnings.

## Adding New Stubs

When adding type stubs for a new library:

1. Create a directory named `<library-name>-stubs/` in this directory
2. Create `__init__.pyi` and any module-specific `.pyi` files
3. Follow PEP 484 type stub conventions
4. Document the stub in this README

## Type Stub Packages

Official type stub packages (from PyPI) are preferred over custom stubs. These are installed via `pyproject.toml`:
- `types-requests` - Type stubs for requests library
- `types-urllib3` - Type stubs for urllib3 library

See `pyproject.toml` for the complete list of type stub dependencies.

