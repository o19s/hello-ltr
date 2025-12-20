# Hello LTR :)

The overall goal of this project is to demonstrate all the steps required to work with LTR in Elasticsearch, Solr, or OpenSearch. There are two modes of running this project. You can run and edit notebooks in a docker container or you can do local development on the notebooks and connect to the search engine(s) running in Docker.

## No fuss setup: You just want to play with LTR

Follow these steps if you're just playing around & are OK with possibly losing some work (all notebooks exist just in the docker container)

With docker simply run

```
docker compose up
```

at the root dir and go to town!

This will run jupyter and all search engines in Docker containers. Check that each is up at the default ports:

- Solr: [localhost:8983](localhost:8983)
- Elasticsearch: [localhost:9200](localhost:9200)
- Kibana: [localhost:5601](localhost:5601)
- OpenSearch: [localhost:9201](localhost:9201)
- OpenSearch Dashboards: [localhost:5602](localhost:5602)
- Jupyter: [localhost:8888](localhost:8888)

## You want to build your own LTR notebooks

Follow these steps if you want to do more serious work with the notebooks. For example, if you want to build a demo with your work's data or something you want to preserve later.

### Run your search engine with Docker

You probably just want to work with one search engine. So whichever one you're working with, launch that search engine in Docker.

#### Running Solr w/ LTR

Setup Solr with docker compose to work with just Solr examples:

```
cd notebooks/solr
docker compose up
```

#### Running Elasticsearch w/ LTR

Setup Elasticsearch with docker compose to work with just Elasticsearch examples:

```
cd notebooks/elasticsearch
docker compose up
```

#### Running OpenSearch w/ LTR

Setup OpenSearch with docker compose to work with just OpenSearch examples:

```
cd notebooks/opensearch
docker compose up
```

### Run Jupyter locally w/ Python 3 and all prereqs

#### Setup Python requirements

- Install `uv` if not already installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Sync the project and dependencies (this will create a virtual environment and install Python if needed): `uv sync`

__Note:__ The above commands should be run from the root folder of the project.

#### Setup Pre-commit Hooks (Recommended)

After setting up Python, install pre-commit hooks to ensure code quality:

```bash
./setup-git-hooks.sh
```

This will automatically run linting and formatting checks before commits. See the [Pre-commit Hooks](#pre-commit-hooks) section below for details on how to skip hooks when needed.

#### Start Jupyter notebook and confirm operation

- Run `uv run jupyter notebook` (or activate the venv with `source .venv/bin/activate` and then run `jupyter notebook`)
- Browse to notebooks/{search\_engine}/{collection} 
- Open the appropriate notebook for your search engine, run each cell, and ensure you get a graph at the last cell:
  - "hello-ltr (Solr).ipynb"
  - "hello-ltr (ES).ipynb"
  - "hello-ltr (OpenSearch).ipynb"

## Tests

The project includes a comprehensive test suite for validating notebook execution and core functionality. For detailed testing documentation, see [`tests/README.md`](tests/README.md).

### Quick Start

To run the full test suite:

```bash
./tests/test.sh
```

This automatically syncs dependencies, starts Docker containers, runs all tests, and cleans up containers.

For more testing options, examples, and troubleshooting, see the [Test Suite Documentation](tests/README.md).

## Development Setup

### Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality. The hooks automatically:
- Run `ruff` for linting and formatting Python code and notebooks
- Check that notebook outputs are stripped (using `nbstripout`)
- Optionally lint commit messages (using `commitizen`)

#### Initial Setup

1. Install pre-commit (if not already installed):
   ```bash
   uv pip install pre-commit
   ```

2. Install the git hooks:
   ```bash
   ./setup-git-hooks.sh
   ```

   This will:
   - Install the pre-commit hooks
   - Set up a commit-msg hook that enables skipping hooks via commit message

#### Using Pre-commit Hooks

Hooks run automatically on `git commit`. To skip hooks, you have several options:

1. **Skip via commit message** (recommended - set up git alias):
   ```bash
   # One-time setup: create git alias
   git config alias.commit '!./git-commit-wrapper.sh'
   
   # Then use normally:
   git commit -m "Your message [skip lint]"
   ```
   Or use the wrapper script directly:
   ```bash
   ./git-commit-wrapper.sh -m "Your message [skip lint]"
   ```
   This skips ruff linting/formatting and notebook checks.

2. **Skip specific hooks using SKIP environment variable**:
   ```bash
   SKIP=ruff,notebooks git commit
   ```

3. **Skip all hooks**:
   ```bash
   git commit --no-verify
   ```

#### Manual Hook Execution

You can manually run hooks on all files:
```bash
pre-commit run --all-files
```

Or run a specific hook:
```bash
pre-commit run ruff --all-files
pre-commit run notebook-output-check --all-files
```

### Code Standards

This project follows PEP 8 naming conventions. For detailed guidelines and examples, see [`NAMING_CONVENTIONS.md`](NAMING_CONVENTIONS.md).

Key points:
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Naming violations are automatically checked by ruff in CI/CD

For a complete audit of existing violations and their justifications, see [`NAMING_CONVENTIONS_VIOLATIONS.md`](NAMING_CONVENTIONS_VIOLATIONS.md).

### Quality Check Script

The project includes a quality check script for validating code and notebooks:

**Script:** `tests/check_quality.sh`

**Features:**
- Comprehensive quality checks for code and notebooks
- Can run all checks or filter by type
- Supports auto-fixing issues

**Options:**
- `--fix`: Auto-fix issues where possible
- `--notebooks-only`: Only check notebooks
- `--code-only`: Only check Python code

**Checks Performed:**
1. Ruff linting (Python code and notebooks)
2. Ruff formatting (Python code and notebooks)
3. Notebook output stripping verification (`nbstripout --check`)

**Usage Examples:**
```bash
# Check everything
./tests/check_quality.sh

# Check and auto-fix
./tests/check_quality.sh --fix

# Check only notebooks
./tests/check_quality.sh --notebooks-only

# Check only Python code
./tests/check_quality.sh --code-only
```

**Exit Codes:**
- `0`: All checks passed
- `1`: One or more checks failed

### Daily Development Workflow

**Typical workflow:**
```bash
# Pre-commit hooks run automatically on git commit
git commit -m "feat: add new feature"

# Skip hooks when needed
git commit -m "wip: work in progress [skip lint]"
SKIP=ruff git commit -m "quick fix"
git commit --no-verify -m "emergency fix"

# Run quality checks manually
./tests/check_quality.sh
./tests/check_quality.sh --fix
```

### CI/CD

The project uses GitHub Actions for continuous integration. For detailed CI/CD documentation, see [`.github/README.md`](.github/README.md).

**What's automated:**
- ✅ Naming convention enforcement (PEP 8)
- ✅ Unit/integration test execution
- ✅ Code coverage reporting
- ✅ Dependency update automation (Dependabot)

## Documentation

For comprehensive documentation, see:

- **[Architecture Documentation](ARCHITECTURE.md)** - System architecture, design patterns, and component overview
- **[Architecture Decision Records](adr/README.md)** - Historical record of key architectural decisions
- **[Codebase Review](CODEBASE_REVIEW.md)** - Complete code quality and security analysis
- **[CI/CD Documentation](.github/README.md)** - GitHub Actions workflows and Dependabot configuration
- **[Type Aliases Guide](TYPE_ALIASES_GUIDE.md)** - Type system documentation and usage
- **[Test Suite Documentation](tests/README.md)** - Testing infrastructure and usage
- **[Naming Conventions](NAMING_CONVENTIONS.md)** - Code style guidelines
