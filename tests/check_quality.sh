#!/bin/bash
#
# Code quality checks for hello-ltr
#
# Usage:
#   ./tests/check_quality.sh [OPTIONS]
#
# Options:
#   --fix          Auto-fix issues where possible (for ruff)
#   --notebooks-only  Only check notebooks
#   --code-only    Only check Python code (exclude notebooks)
#
# This script runs:
#   - ruff check: Linting for Python code and notebooks
#   - ruff format --check: Formatting check for Python code and notebooks
#   - nbstripout --check: Check that notebook outputs are stripped
#
# Exit codes:
#   0: All checks passed
#   1: One or more checks failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

FIX=false
NOTEBOOKS_ONLY=false
CODE_ONLY=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --fix)
            FIX=true
            shift
            ;;
        --notebooks-only)
            NOTEBOOKS_ONLY=true
            shift
            ;;
        --code-only)
            CODE_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Usage: $0 [--fix] [--notebooks-only] [--code-only]"
            exit 1
            ;;
    esac
done

# Validate mutually exclusive options
if [ "$NOTEBOOKS_ONLY" = true ] && [ "$CODE_ONLY" = true ]; then
    echo "Error: --notebooks-only and --code-only are mutually exclusive"
    exit 1
fi

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "Error: ruff is not installed"
    echo "Install it with: uv pip install ruff"
    exit 1
fi

# Check if nbstripout is installed
if ! command -v nbstripout &> /dev/null; then
    echo "Error: nbstripout is not installed"
    echo "Install it with: uv pip install nbstripout"
    exit 1
fi

ERRORS=0

echo "================================================"
echo "== Code Quality Checks"
echo "================================================"
echo ""

# Run ruff checks
if [ "$CODE_ONLY" = false ]; then
    echo "[$(date +%H:%M:%S)] Checking notebooks with ruff..."
    if [ "$FIX" = true ]; then
        if ruff check --fix notebooks/; then
            echo "✓ Notebook linting passed (with fixes)"
        else
            echo "✗ Notebook linting failed"
            ERRORS=$((ERRORS + 1))
        fi
    else
        if ruff check notebooks/; then
            echo "✓ Notebook linting passed"
        else
            echo "✗ Notebook linting failed"
            ERRORS=$((ERRORS + 1))
        fi
    fi
    
    echo "[$(date +%H:%M:%S)] Checking notebook formatting..."
    if [ "$FIX" = true ]; then
        if ruff format notebooks/; then
            echo "✓ Notebook formatting passed (with fixes)"
        else
            echo "✗ Notebook formatting failed"
            ERRORS=$((ERRORS + 1))
        fi
    else
        if ruff format --check notebooks/; then
            echo "✓ Notebook formatting passed"
        else
            echo "✗ Notebook formatting failed (run with --fix to auto-fix)"
            ERRORS=$((ERRORS + 1))
        fi
    fi
    
    echo "[$(date +%H:%M:%S)] Checking notebook outputs are stripped..."
    if nbstripout --check notebooks/ > /dev/null 2>&1; then
        echo "✓ Notebook outputs are properly stripped"
    else
        echo "✗ Some notebooks have outputs (run: nbstripout notebooks/)"
        ERRORS=$((ERRORS + 1))
    fi
fi

if [ "$NOTEBOOKS_ONLY" = false ]; then
    echo "[$(date +%H:%M:%S)] Checking Python code with ruff..."
    if [ "$FIX" = true ]; then
        if ruff check --fix ltr/ rre/ utils/ tests/ *.py; then
            echo "✓ Python code linting passed (with fixes)"
        else
            echo "✗ Python code linting failed"
            ERRORS=$((ERRORS + 1))
        fi
    else
        if ruff check ltr/ rre/ utils/ tests/ *.py; then
            echo "✓ Python code linting passed"
        else
            echo "✗ Python code linting failed"
            ERRORS=$((ERRORS + 1))
        fi
    fi
    
    echo "[$(date +%H:%M:%S)] Checking Python code formatting..."
    if [ "$FIX" = true ]; then
        if ruff format ltr/ rre/ utils/ tests/ *.py; then
            echo "✓ Python code formatting passed (with fixes)"
        else
            echo "✗ Python code formatting failed"
            ERRORS=$((ERRORS + 1))
        fi
    else
        if ruff format --check ltr/ rre/ utils/ tests/ *.py; then
            echo "✓ Python code formatting passed"
        else
            echo "✗ Python code formatting failed (run with --fix to auto-fix)"
            ERRORS=$((ERRORS + 1))
        fi
    fi
fi

echo ""
echo "================================================"
if [ $ERRORS -eq 0 ]; then
    echo "== All quality checks passed ✓"
    echo "================================================"
    exit 0
else
    echo "== Quality checks failed ($ERRORS error(s))"
    echo "================================================"
    echo ""
    echo "To fix issues automatically:"
    echo "  ./tests/check_quality.sh --fix"
    echo ""
    echo "To fix notebook formatting:"
    echo "  ruff format notebooks/"
    echo ""
    echo "To strip notebook outputs:"
    echo "  nbstripout notebooks/"
    exit 1
fi

