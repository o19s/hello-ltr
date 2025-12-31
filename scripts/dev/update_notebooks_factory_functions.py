#!/usr/bin/env python3
"""
Update notebooks to use factory functions instead of direct client instantiation.

This script updates all notebooks to use factory functions from ltr.client:
- SolrClient() -> create_solr_client()
- ElasticClient() -> create_elastic_client()
- OpenSearchClient() -> create_opensearch_client()

It handles various import patterns and preserves configs_dir parameters.
"""

import json
import sys
from pathlib import Path


def update_notebook(notebook_path: Path) -> bool:
    """Update a single notebook to use factory functions.

    Args:
        notebook_path: Path to the notebook file

    Returns:
        bool: True if notebook was updated, False otherwise
    """
    with open(notebook_path) as f:
        nb = json.load(f)

    updated = False

    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue

        source_lines = cell["source"]
        new_source = []
        cell_updated = False

        for line in source_lines:
            # Handle Solr imports and instantiation
            if "from ltr.client.solr_client import SolrClient" in line:
                line = "from ltr.client import create_solr_client\n"
                cell_updated = True
            elif (
                "from ltr.client import SolrClient" in line
                and "create_solr_client" not in "".join(source_lines)
            ):
                # Only replace if create_solr_client is not already imported
                line = line.replace("SolrClient", "create_solr_client")
                cell_updated = True
            elif "client = SolrClient()" in line:
                line = line.replace("SolrClient()", "create_solr_client()")
                cell_updated = True

            # Handle Elasticsearch imports and instantiation
            elif "from ltr.client.elastic_client import ElasticClient" in line:
                line = "from ltr.client import create_elastic_client\n"
                cell_updated = True
            elif (
                "from ltr.client import ElasticClient" in line
                and "create_elastic_client" not in "".join(source_lines)
            ):
                # Only replace if create_elastic_client is not already imported
                line = line.replace("ElasticClient", "create_elastic_client")
                cell_updated = True
            elif "client = ElasticClient()" in line:
                line = line.replace("ElasticClient()", "create_elastic_client()")
                cell_updated = True
            elif "client = client.ElasticClient()" in line:
                # Handle case where ltr.client is imported as client
                line = line.replace("client.ElasticClient()", "create_elastic_client()")
                # Add import if not present
                if "from ltr.client import create_elastic_client" not in "".join(
                    new_source
                ):
                    # Find where to insert import (after other imports)
                    insert_idx = len(new_source)
                    for j, prev_line in enumerate(new_source):
                        if "import" in prev_line and j < len(new_source) - 1:
                            insert_idx = j + 1
                    new_source.insert(
                        insert_idx, "from ltr.client import create_elastic_client\n"
                    )
                cell_updated = True
            elif "ElasticClient(configs_dir" in line:
                # Handle ElasticClient(configs_dir=...) pattern
                # Extract configs_dir value
                if "configs_dir=" in line:
                    # Try to extract the configs_dir parameter
                    import re

                    match = re.search(
                        r'ElasticClient\(configs_dir=["\']?([^"\']+)["\']?\)', line
                    )
                    if match:
                        configs_dir_val = match.group(1)
                        line = line.replace(
                            f'ElasticClient(configs_dir="{configs_dir_val}")',
                            f'create_elastic_client(configs_dir="{configs_dir_val}")',
                        )
                        line = line.replace(
                            f"ElasticClient(configs_dir='{configs_dir_val}')",
                            f"create_elastic_client(configs_dir='{configs_dir_val}')",
                        )
                        cell_updated = True
                else:
                    line = line.replace("ElasticClient(", "create_elastic_client(")
                    cell_updated = True

            # Handle OpenSearch imports and instantiation
            elif "from ltr.client.opensearch_client import OpenSearchClient" in line:
                line = "from ltr.client import create_opensearch_client\n"
                cell_updated = True
            elif (
                "from ltr.client import OpenSearchClient" in line
                and "create_opensearch_client" not in "".join(source_lines)
            ):
                # Only replace if create_opensearch_client is not already imported
                line = line.replace("OpenSearchClient", "create_opensearch_client")
                cell_updated = True
            elif "client = OpenSearchClient()" in line:
                line = line.replace("OpenSearchClient()", "create_opensearch_client()")
                cell_updated = True
            elif "client = client.OpenSearchClient()" in line:
                # Handle case where ltr.client is imported as client
                line = line.replace(
                    "client.OpenSearchClient()", "create_opensearch_client()"
                )
                # Add import if not present
                if "from ltr.client import create_opensearch_client" not in "".join(
                    new_source
                ):
                    # Find where to insert import (after other imports)
                    insert_idx = len(new_source)
                    for j, prev_line in enumerate(new_source):
                        if "import" in prev_line and j < len(new_source) - 1:
                            insert_idx = j + 1
                    new_source.insert(
                        insert_idx, "from ltr.client import create_opensearch_client\n"
                    )
                cell_updated = True
            elif "OpenSearchClient(configs_dir" in line:
                # Handle OpenSearchClient(configs_dir=...) pattern
                import re

                match = re.search(
                    r'OpenSearchClient\(configs_dir=["\']?([^"\']+)["\']?\)', line
                )
                if match:
                    configs_dir_val = match.group(1)
                    line = line.replace(
                        f'OpenSearchClient(configs_dir="{configs_dir_val}")',
                        f'create_opensearch_client(configs_dir="{configs_dir_val}")',
                    )
                    line = line.replace(
                        f"OpenSearchClient(configs_dir='{configs_dir_val}')",
                        f"create_opensearch_client(configs_dir='{configs_dir_val}')",
                    )
                    cell_updated = True
                else:
                    line = line.replace(
                        "OpenSearchClient(", "create_opensearch_client("
                    )
                    cell_updated = True

            new_source.append(line)

        if cell_updated:
            cell["source"] = new_source
            updated = True

    if updated:
        with open(notebook_path, "w") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
        return True

    return False


def main():
    """Update all notebooks in the notebooks directory."""
    repo_root = Path(__file__).parent.parent.parent
    notebooks_dir = repo_root / "notebooks"

    if not notebooks_dir.exists():
        print(f"Error: Notebooks directory not found: {notebooks_dir}")
        sys.exit(1)

    updated_count = 0
    total_count = 0

    # Find all notebook files
    for notebook_path in notebooks_dir.rglob("*.ipynb"):
        total_count += 1
        try:
            if update_notebook(notebook_path):
                print(f"Updated: {notebook_path.relative_to(repo_root)}")
                updated_count += 1
        except Exception as e:
            print(f"Error updating {notebook_path}: {e}", file=sys.stderr)

    print(f"\nUpdated {updated_count} out of {total_count} notebooks")


if __name__ == "__main__":
    main()
