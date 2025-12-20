# CI/CD Documentation

This directory contains GitHub Actions workflows and Dependabot configuration for automated testing, linting, and dependency management.

## Workflows

### Lint Naming Conventions (`.github/workflows/lint-naming.yml`)

**Purpose:** Enforces PEP 8 naming conventions across the codebase.

**Triggers:**
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches

**What it does:**
- Runs on Ubuntu latest with Python 3.9
- Uses `uv` for dependency management
- Checks PEP 8 naming conventions with Ruff (`--select N`)
- Validates both Python code (`ltr/`, `rre/`, `utils/`, `tests/`, `*.py`) and notebooks (`notebooks/`)
- Fails on naming violations (`continue-on-error: false`)

### Tests (`.github/workflows/tests.yml`)

**Purpose:** Runs unit and integration tests with coverage reporting.

**Triggers:**
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches

**What it does:**
- Runs on Ubuntu latest with Python 3.9
- Uses `uv` for dependency management
- Sets up Docker service for container-based tests
- Runs unit tests (`tests/unit/`) with coverage
- Runs integration tests (`tests/integration/`) with coverage
- Generates coverage reports (XML, HTML, terminal)
- Uploads coverage to Codecov
- Uploads coverage HTML and test results as artifacts (30-day retention)
- Publishes coverage summary to GitHub Actions summary

**Artifacts:**
- `coverage-report`: HTML coverage report
- `test-results`: JUnit XML test results

## Dependabot

### Configuration (`.github/dependabot.yml`)

**Purpose:** Automatically creates pull requests for dependency updates.

**Schedule:**
- Weekly on Mondays at 09:00

**Features:**
- Automatic dependency updates for Python packages
- Groups related packages:
  - `test-dependencies`: pytest and related packages
  - `code-quality`: ruff, pre-commit, pyright
- Limits open PRs to 10
- Ignores major version updates for critical dependencies:
  - elasticsearch
  - opensearch-py
  - numpy
  - pandas
  - scikit-learn
  - xgboost
- Custom commit message prefix (`deps`) and labels (`dependencies`, `python`)

**Note:** After merging a Dependabot PR, run `uv lock` to sync the lock file.

## Pipeline Flow

```
Developer commits → Pre-commit hooks run locally
                  ↓
Push to GitHub → GitHub Actions triggered
               ↓
Lint checks run (Ruff --select N)
Tests run (unit + integration with coverage)
               ↓
Pass: Merge allowed
Fail: Fix required
```

## Viewing Results

- **Workflow runs:** Go to the "Actions" tab in GitHub
- **Coverage reports:** Download the `coverage-report` artifact or view on Codecov (if configured)
- **Test results:** Download the `test-results` artifact or view in the workflow summary

## Future Enhancements

**High Priority:**
- Security scanning (Bandit, pip-audit)
- Full linting checks (not just naming)
- Type checking in CI

**Medium Priority:**
- Docker image building and publishing
- More comprehensive linting (full ruff check, formatting checks)

**Low Priority:**
- Performance benchmarks
- Documentation building and deployment
- Release automation

