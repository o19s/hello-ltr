"""RRE (Ranking Relevance Evaluation) integration.

This module provides functions for running RRE evaluations using Docker
and displaying evaluation results in Jupyter notebooks.
"""

import json
import shlex
import subprocess

import plotly.graph_objs as go
from plotly.offline import init_notebook_mode, iplot

from ltr.logger import get_logger

logger = get_logger(__name__)


def log_run(cmd: str) -> None:
    """Run a shell command and print its output.

    Args:
        cmd: Command string to execute.

    Returns:
        None: Output is printed to stdout/stderr.
    """
    result = subprocess.run(
        shlex.split(cmd),
        capture_output=True,
        text=True,
        check=False,
    )
    logger.info(result.stdout)
    if result.stderr:
        logger.error(result.stderr)


def quiet_run(cmd: str) -> None:
    """Run a shell command silently without printing output.

    Args:
        cmd: Command string to execute.

    Returns:
        None: Command output is captured but not displayed.
    """
    subprocess.run(
        shlex.split(cmd),
        capture_output=True,
        text=True,
        check=False,
    )


def evaluate(mode: str) -> None:
    """Run RRE (Ranking Relevance Evaluation) using Docker.

    Builds a Docker image, runs the evaluation, and copies results to the
    data directory.

    Args:
        mode: Search engine mode, one of: "elastic", "solr", "opensearch".

    Returns:
        None: Results are written to:
            - data/rre-evaluation.json
            - data/rre-report.xlsx

    Raises:
        ValueError: If mode is not one of the supported values.

    Note:
        This function requires Docker to be installed and running.
        The evaluation process can take a significant amount of time.
    """
    # Build the docker image
    acceptable_modes = ["elastic", "solr", "opensearch"]
    if mode not in acceptable_modes:
        raise ValueError(
            f"{mode} is not a supported value for mode. must be one of {acceptable_modes}"
        )

    cmd = f"docker build --no-cache -t ltr-rre rre/{mode}/."

    logger.info("Building RRE image - This will take a while")
    quiet_run(cmd)

    # Remove and run a fresh docker image
    cmd = "docker rm -f ltr-rre"
    quiet_run(cmd)

    cmd = "docker run --name ltr-rre ltr-rre"
    logger.info("Running evaluation")
    log_run(cmd)

    # Copy out reports
    cmd = "docker cp ltr-rre:/rre/target/rre/evaluation.json data/rre-evaluation.json"
    log_run(cmd)

    cmd = "docker cp ltr-rre:/rre/target/site/rre-report.xlsx data/rre-report.xlsx"
    log_run(cmd)

    logger.info("RRE Evaluation complete")


def rre_table() -> None:
    """Display RRE evaluation results as an interactive table in Jupyter.

    Loads evaluation results from data/rre-evaluation.json and displays
    precision, recall, and ERR@30 metrics for baseline, classic, and latest
    experiments in a Plotly table.

    Returns:
        None: Table is displayed in the notebook output.

    Raises:
        FileNotFoundError: If data/rre-evaluation.json doesn't exist.
        KeyError: If expected metrics are missing from the evaluation file.

    Note:
        This function is designed for use in Jupyter notebooks and requires
        plotly to be installed.
    """
    init_notebook_mode(connected=True)

    with open("data/rre-evaluation.json") as src:
        report = json.load(src)
        metrics = report["metrics"]

    experiments = ["baseline", "classic", "latest"]
    precisions = []
    recalls = []
    errs = []

    for exp in experiments:
        precisions.append(metrics["P"]["versions"][exp]["value"])
        recalls.append(metrics["R"]["versions"][exp]["value"])
        errs.append(metrics["ERR@30"]["versions"][exp]["value"])

    trace = go.Table(
        header={
            "values": ["", "Precision", "Recall", "ERR"],
            "fill": {"color": "#AAAAAA"},
        },
        cells={"values": [experiments, precisions, recalls, errs]},
    )

    data = [trace]
    iplot(data)
