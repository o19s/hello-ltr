#!/bin/bash
# Setup script for git hooks to enable [skip lint] functionality
# This installs the commit-msg hook that checks for skip patterns

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_HOOKS_DIR="$SCRIPT_DIR/.githooks"
GIT_DIR="$SCRIPT_DIR/.git/hooks"

echo "Setting up git hooks..."

# Check if .git directory exists
if [ ! -d "$SCRIPT_DIR/.git" ]; then
    echo "Error: .git directory not found. Are you in a git repository?"
    exit 1
fi

# Install pre-commit hook using pre-commit framework
# Note: commit-msg hook is automatically installed by pre-commit for commitizen
if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit hooks..."
    pre-commit install
    echo "✓ Pre-commit hooks installed"
else
    echo "Warning: pre-commit not found. Install it with: uv pip install pre-commit"
    echo "Or: pip install pre-commit"
fi

echo ""
echo "Setup complete!"
echo ""
echo "You can skip hooks using commit message patterns in several ways:"
echo ""
echo "1. Use the wrapper script:"
echo "   ./git-commit-wrapper.sh -m 'Your message [skip lint]'"
echo ""
echo "2. Set up a git alias (recommended):"
echo "   git config alias.commit '!./git-commit-wrapper.sh'"
echo "   Then use: git commit -m 'Your message [skip lint]'"
echo ""
echo "3. Use environment variable:"
echo "   SKIP=ruff,notebooks git commit"
echo ""
echo "4. Skip all hooks:"
echo "   git commit --no-verify"

