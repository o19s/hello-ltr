#!/bin/bash
# Wrapper script for git commit that enables [skip lint] functionality
# Usage: ./git-commit-wrapper.sh [git commit arguments]
# Or create a git alias: git config alias.commit '!./git-commit-wrapper.sh'

# Check if commit message is provided via -m flag
SKIP_HOOKS=false
ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--message)
            # Check the message for skip patterns
            if echo "$2" | grep -qiE "\[skip\s+(lint|all|pre-commit)\]"; then
                SKIP_HOOKS=true
                SKIP_VALUE="ruff,ruff-format,notebook-output-check"
            fi
            ARGS+=("$1" "$2")
            shift 2
            ;;
        -F|--file)
            # Check the file for skip patterns
            if [ -f "$2" ]; then
                if grep -qiE "\[skip\s+(lint|all|pre-commit)\]" "$2"; then
                    SKIP_HOOKS=true
                    SKIP_VALUE="ruff,ruff-format,notebook-output-check"
                fi
            fi
            ARGS+=("$1" "$2")
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

# If skip pattern found, set SKIP environment variable
if [ "$SKIP_HOOKS" = true ]; then
    echo "Note: [skip lint] detected. Skipping ruff and notebook checks."
    SKIP="$SKIP_VALUE" git commit "${ARGS[@]}"
else
    # Run git commit normally
    git commit "${ARGS[@]}"
fi

