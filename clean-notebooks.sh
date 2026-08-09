#!/bin/bash

# Removes all output and metadata from notebooks
# Use nbstripout from venv if available, otherwise try system-wide
if [ -f ".venv/bin/nbstripout" ]; then
    NBSTRIPOUT=".venv/bin/nbstripout"
elif command -v nbstripout &> /dev/null; then
    NBSTRIPOUT="nbstripout"
else
    echo "Error: nbstripout not found. Please install it with: uv sync"
    exit 1
fi

find notebooks -type f -name "*.ipynb" -print0 | xargs -0 "$NBSTRIPOUT"
