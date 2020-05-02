#!/bin/bash

# Removes all output and metadata from notebooks
find notebooks -type f -name "*.ipynb" -print0 | xargs -0 nbstripout
