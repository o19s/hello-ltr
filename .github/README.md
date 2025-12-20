# CI/CD Documentation

This directory contains GitHub Actions workflows and Dependabot configuration for automated testing, linting, and dependency management.

## Workflows

All workflows can be manually triggered via `workflow_dispatch` in the GitHub Actions UI.

### Tests (`.github/workflows/tests.yml`)

**Purpose:** Runs unit and integration tests with coverage reporting.

**Triggers:**
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches
- Manual trigger (`workflow_dispatch`)

**What it does:**
- Runs on Ubuntu latest with Python 3.9
- Uses `uv` for dependency management
- Sets up Docker service for container-based tests
- Runs unit tests (`tests/unit/`) with coverage
- Runs integration tests (`tests/integration/`) with coverage
- Generates coverage reports (XML, HTML, terminal)
- Uploads coverage to Codecov
- Uploads coverage HTML and test results as artifacts (30-day retention)
- Publishes coverage summary and build time to GitHub Actions summary

**Artifacts:**
- `coverage-report`: HTML coverage report
- `test-results`: JUnit XML test results

### Type Check (`.github/workflows/type-check.yml`)

**Purpose:** Runs static type checking with Pyright.

**Triggers:**
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches
- Manual trigger (`workflow_dispatch`)

**What it does:**
- Runs on Ubuntu latest with Python 3.9
- Uses `uv` for dependency management
- Runs Pyright type checking on all Python code
- Tracks and reports build time

### Full Linting (`.github/workflows/lint-full.yml`)

**Purpose:** Runs comprehensive linting and formatting checks with Ruff.

**Triggers:**
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches
- Manual trigger (`workflow_dispatch`)

**What it does:**
- Runs on Ubuntu latest with Python 3.9
- Uses `uv` for dependency management
- Runs full Ruff linting checks (all rules, including PEP 8 naming conventions)
- Checks Ruff formatting on Python code and notebooks
- Validates both Python code (`ltr/`, `rre/`, `utils/`, `tests/`, `*.py`) and notebooks (`notebooks/`)
- Tracks and reports build time

**Note:** This workflow replaces the previous `lint-naming.yml` workflow, as it covers all linting rules including naming conventions.

### Security Scan (`.github/workflows/security-scan.yml`)

**Purpose:** Scans code and dependencies for security vulnerabilities.

**Triggers:**
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches
- Manual trigger (`workflow_dispatch`)
- Scheduled: Weekly on Mondays at 09:00 UTC

**What it does:**
- Runs on Ubuntu latest with Python 3.9
- Uses `uv` for dependency management
- Runs Bandit security scan on Python code
- Runs pip-audit to check for vulnerable dependencies
- Uploads security scan reports as artifacts (30-day retention)
- Tracks and reports build time

**Artifacts:**
- `security-reports`: JSON reports from Bandit and pip-audit

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
┌─────────────────────────────────────────┐
│  Parallel Workflow Execution:          │
│  • Full Linting (Ruff all rules + format)│
│  • Type Check (Pyright)                 │
│  • Tests (unit + integration + coverage)│
│  • Security Scan (Bandit + pip-audit)  │
└─────────────────────────────────────────┘
               ↓
Pass: Merge allowed
Fail: Fix required
```

## Viewing Results

- **Workflow runs:** Go to the "Actions" tab in GitHub
- **Coverage reports:** Download the `coverage-report` artifact or view on Codecov (if configured)
- **Test results:** Download the `test-results` artifact or view in the workflow summary

## Build Time Tracking

All workflows now track and report build times:
- Build time is calculated from workflow start to completion
- Displayed in GitHub Actions step summary
- Can be measured via `measure_dev_metrics.py` script

## Future Enhancements

**Medium Priority:**
- Docker image building and publishing
- Performance benchmarks
- Documentation building and deployment

**Low Priority:**
- Release automation
- Matrix testing across Python versions
- Cross-platform testing (Windows, macOS)

