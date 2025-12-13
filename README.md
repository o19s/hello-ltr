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

### Automatically run everything...

NB: It may be necessary to increase the number of open files on MacOS to a
higher value than the default 256 for the tests to complete successfully. Use:

$ ulimit -n 4096

to increase the value to a sensible amount.

To run a full suite of tests, such as to verify a PR, you can simply run

```bash
./tests/test.sh
```

This will automatically:
- Sync dependencies with `uv`
- Start Docker containers per pytest worker (isolated containers for parallel execution)
- Run all notebook tests via pytest
- Clean up containers after tests complete

Failing tests will have their output in `tests/last_run.ipynb`

**Note:** Containers are automatically managed by pytest fixtures. Each worker gets isolated containers with unique ports to prevent conflicts. See `tests/README.md` for advanced usage.

### While developing...

For more informal development:

- Run tests directly:
  ```bash
  ./tests/test.sh
  # or
  pytest tests/notebooks/test_notebooks.py
  ```

- Filter tests by engine:
  ```bash
  pytest -k solr tests/notebooks/test_notebooks.py
  pytest -k opensearch tests/notebooks/test_notebooks.py
  pytest -k elasticsearch tests/notebooks/test_notebooks.py
  ```

- Run specific notebooks:
  ```bash
  pytest tests/notebooks/test_notebooks.py::test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb]
  ```

- Re-run only failed tests:
  ```bash
  pytest --lf tests/notebooks/test_notebooks.py
  ```

- Tests fail if notebooks return any errors
  - The failing notebook will be stored at `tests/last_run.ipynb`

**Note:** Pre-commit hooks will run automatically on `git commit`. To skip hooks, use `git commit -m "message [skip lint]"` (after setting up the git alias) or `git commit --no-verify`. See [Pre-commit Hooks](#pre-commit-hooks) section for details.

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
