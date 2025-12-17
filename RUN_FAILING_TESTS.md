# Running Failing Notebook Tests

This guide explains how to run failing notebook tests in batches by engine type.

## Quick Start

### Run All Failing Notebooks by Engine

```bash
# OpenSearch (9 failing notebooks)
uv run python analyze_notebook_tests.py --failing-only --engine opensearch --batch-size 3

# Elasticsearch (10 failing notebooks)  
uv run python analyze_notebook_tests.py --failing-only --engine elasticsearch --batch-size 3

# Solr (4 failing notebooks)
uv run python analyze_notebook_tests.py --failing-only --engine solr --batch-size 2
```

### Run Specific Batch

```bash
# Run notebooks 0-2 (first batch)
uv run python analyze_notebook_tests.py --failing-only --engine opensearch --start 0 --end 3

# Run notebooks 3-5 (second batch)
uv run python analyze_notebook_tests.py --failing-only --engine opensearch --start 3 --end 6
```

### Run Single Notebook

```bash
uv run python analyze_notebook_tests.py --failing-only --engine opensearch --limit 1
```

## Options

- `--failing-only`: Run only notebooks from the failing list
- `--engine`: Filter by engine type (opensearch, elasticsearch, solr)
- `--batch-size N`: Process notebooks in batches of N
- `--start N`: Start from index N
- `--end N`: End at index N
- `--limit N`: Limit to N notebooks total

## Output

- Real-time cell-by-cell logging (shows which cell is executing and the code)
- Detailed error analysis for each failure
- JSON results saved to `notebook_test_analysis.json` (or `notebook_test_analysis_batch_N.json` for batches)
- Summary report at the end

## Notes

- Each test can take up to 10 minutes
- Tests require Docker containers to be running externally (use `./tests/test.sh` to start containers)
- The script automatically sets `USE_WORKER_CONTAINERS=false` to avoid port conflicts when running sequential tests
- Cell logs show: cell number, timestamp, and code preview (first 5 lines)
- If you see port conflict errors, ensure containers are started via `./tests/test.sh` or manually

