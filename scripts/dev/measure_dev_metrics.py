#!/usr/bin/env python3
"""
Development Metrics Measurement Script

Measures key development metrics:
- CI/CD build time (from GitHub Actions workflow runs)
- Time from PR to merge (from GitHub pull requests)
- Bug escape rate (from GitHub issues)

Usage:
    python measure_dev_metrics.py                    # Measure all metrics
    python measure_dev_metrics.py --ci-only           # CI/CD build time only
    python measure_dev_metrics.py --pr-only           # PR merge time only
    python measure_dev_metrics.py --bugs-only         # Bug escape rate only
    python measure_dev_metrics.py --output json       # Output as JSON
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Any


def get_repo_info() -> tuple[str, str]:
    """Get repository owner and name from git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Handle both https://github.com/owner/repo.git and git@github.com:owner/repo.git
        if url.startswith("https://"):
            parts = (
                url.replace("https://github.com/", "").replace(".git", "").split("/")
            )
        elif url.startswith("git@"):
            parts = url.replace("git@github.com:", "").replace(".git", "").split("/")
        else:
            raise ValueError(f"Unknown git remote format: {url}")

        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Could not parse repo from URL: {url}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get git remote: {e}") from e


def run_gh_command(cmd: list[str]) -> dict[str, Any] | list[dict[str, Any]]:
    """Run a GitHub CLI command and return parsed JSON."""
    try:
        result = subprocess.run(
            ["gh"] + cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and "not found" in e.stderr.lower():
            raise RuntimeError(
                "GitHub CLI (gh) not authenticated. Run 'gh auth login' first."
            ) from e
        raise RuntimeError(f"GitHub CLI command failed: {e.stderr}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GitHub CLI output: {e}") from e


def measure_ci_build_time(owner: str, repo: str, days: int = 30) -> dict[str, Any]:
    """Measure average CI/CD build time from recent workflow runs."""
    print(f"Measuring CI/CD build times for {owner}/{repo} (last {days} days)...")

    workflows = run_gh_command(
        [
            "api",
            f"repos/{owner}/{repo}/actions/workflows",
            "--jq",
            '.workflows[] | select(.state == "active") | {id: .id, name: .name, path: .path}',
        ]
    )

    if not workflows:
        return {
            "status": "no_workflows",
            "message": "No active workflows found",
            "average_build_time_seconds": None,
            "average_build_time_minutes": None,
            "workflow_runs": [],
        }

    # Get workflow runs for the last N days
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    all_runs = []
    total_duration = 0
    successful_runs = 0

    for workflow in workflows:
        workflow_id = workflow["id"]  # type: ignore[literal-required]
        workflow_name = workflow["name"]  # type: ignore[literal-required]

        runs = run_gh_command(
            [
                "api",
                f"repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs",
                "--jq",
                f'.workflow_runs[] | select(.created_at >= "{cutoff_date}" and .status == "completed" and .conclusion == "success") | {{id: .id, name: .name, created_at: .created_at, updated_at: .updated_at, duration: ((.updated_at | fromdateiso8601) - (.created_at | fromdateiso8601))}}',
            ]
        )

        if isinstance(runs, list):
            for run in runs:
                if isinstance(run, dict) and "duration" in run and run.get("duration"):
                    duration_seconds: float = float(run["duration"])  # type: ignore[assignment]
                    all_runs.append(
                        {
                            "workflow": workflow_name,
                            "workflow_id": workflow_id,
                            "run_id": run["id"],  # type: ignore[literal-required]
                            "created_at": run["created_at"],  # type: ignore[literal-required]
                            "duration_seconds": duration_seconds,
                            "duration_minutes": round(duration_seconds / 60, 2),
                        }
                    )
                    total_duration += duration_seconds
                    successful_runs += 1

    if successful_runs == 0:
        return {
            "status": "no_runs",
            "message": f"No successful workflow runs found in the last {days} days",
            "average_build_time_seconds": None,
            "average_build_time_minutes": None,
            "workflow_runs": [],
        }

    avg_seconds = total_duration / successful_runs
    avg_minutes = round(avg_seconds / 60, 2)

    return {
        "status": "success",
        "period_days": days,
        "total_runs": successful_runs,
        "average_build_time_seconds": round(avg_seconds, 2),
        "average_build_time_minutes": avg_minutes,
        "total_build_time_seconds": round(total_duration, 2),
        "workflow_runs": sorted(all_runs, key=lambda x: x["created_at"], reverse=True)[
            :10
        ],  # Last 10 runs
    }


def measure_pr_merge_time(owner: str, repo: str, days: int = 90) -> dict[str, Any]:
    """Measure average time from PR creation to merge."""
    print(f"Measuring PR merge times for {owner}/{repo} (last {days} days)...")

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    prs = run_gh_command(
        [
            "api",
            f"repos/{owner}/{repo}/pulls?state=closed&per_page=100",
            "--paginate",
            "--jq",
            f'.[] | select(.merged_at != null and .created_at >= "{cutoff_date}") | {{number: .number, title: .title, created_at: .created_at, merged_at: .merged_at, duration_seconds: ((.merged_at | fromdateiso8601) - (.created_at | fromdateiso8601))}}',
        ]
    )

    if not prs:
        return {
            "status": "no_prs",
            "message": f"No merged PRs found in the last {days} days",
            "average_merge_time_hours": None,
            "average_merge_time_days": None,
            "prs": [],
        }

    total_duration = 0
    pr_data = []

    if isinstance(prs, list):
        for pr in prs:
            if (
                isinstance(pr, dict)
                and "duration_seconds" in pr
                and pr.get("duration_seconds")
            ):
                duration_seconds: float = float(pr["duration_seconds"])  # type: ignore[assignment]
                duration_hours = duration_seconds / 3600
                duration_days = duration_hours / 24

                pr_data.append(
                    {
                        "number": pr["number"],  # type: ignore[literal-required]
                        "title": pr["title"],  # type: ignore[literal-required]
                        "created_at": pr["created_at"],  # type: ignore[literal-required]
                        "merged_at": pr["merged_at"],  # type: ignore[literal-required]
                        "duration_hours": round(duration_hours, 2),
                        "duration_days": round(duration_days, 2),
                    }
                )
                total_duration += duration_seconds

    if not pr_data:
        return {
            "status": "no_valid_prs",
            "message": "No PRs with valid merge times found",
            "average_merge_time_hours": None,
            "average_merge_time_days": None,
            "prs": [],
        }

    avg_seconds = total_duration / len(pr_data)
    avg_hours = avg_seconds / 3600
    avg_days = avg_hours / 24

    return {
        "status": "success",
        "period_days": days,
        "total_prs": len(pr_data),
        "average_merge_time_hours": round(avg_hours, 2),
        "average_merge_time_days": round(avg_days, 2),
        "prs": sorted(pr_data, key=lambda x: x["created_at"], reverse=True)[
            :10
        ],  # Last 10 PRs
    }


def measure_bug_escape_rate(owner: str, repo: str, days: int = 90) -> dict[str, Any]:
    """Measure bug escape rate from GitHub issues."""
    print(f"Measuring bug escape rate for {owner}/{repo} (last {days} days)...")

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    # Get all issues (open and closed) that might be bugs
    # Note: GitHub issues API returns both issues and PRs, so we filter for issues only
    issues = run_gh_command(
        [
            "api",
            f"repos/{owner}/{repo}/issues?state=all&per_page=100",
            "--paginate",
            "--jq",
            f'.[] | select(.pull_request == null and .created_at >= "{cutoff_date}" and ((.labels[]?.name == "bug") or ((.title + " " + (.body // "")) | ascii_downcase | contains("bug")))) | {{number: .number, title: .title, state: .state, created_at: .created_at, closed_at: .closed_at, labels: [.labels[]?.name]}}',
        ]
    )

    if not issues:
        return {
            "status": "no_bugs",
            "message": f"No bug issues found in the last {days} days",
            "total_bugs": 0,
            "bugs_found_in_production": 0,
            "bug_escape_rate": None,
        }

    # Count bugs that were closed (found in production) vs open (found before production)
    # This is a simplified heuristic - in reality, you'd need more sophisticated tracking
    if not isinstance(issues, list):
        issues = []
    total_bugs = len(issues)
    bugs_found_in_production = sum(
        1
        for issue in issues
        if isinstance(issue, dict) and issue.get("state") == "closed"
    )
    bugs_found_before_production = total_bugs - bugs_found_in_production

    escape_rate = (bugs_found_in_production / total_bugs * 100) if total_bugs > 0 else 0

    return {
        "status": "success",
        "period_days": days,
        "total_bugs": total_bugs,
        "bugs_found_in_production": bugs_found_in_production,
        "bugs_found_before_production": bugs_found_before_production,
        "bug_escape_rate_percent": round(escape_rate, 2),
        "note": "Bug escape rate is estimated from GitHub issues. For accurate tracking, consider using issue labels like 'bug:production' vs 'bug:development'",
    }


def format_output(metrics: dict[str, Any], output_format: str) -> None:
    """Format and print metrics output."""
    if output_format == "json":
        print(json.dumps(metrics, indent=2))
    else:
        print("\n" + "=" * 60)
        print("DEVELOPMENT METRICS SUMMARY")
        print("=" * 60 + "\n")

        # CI/CD Build Time
        if "ci_build_time" in metrics:
            ci = metrics["ci_build_time"]
            print("CI/CD Build Time:")
            if ci["status"] == "success":
                print(
                    f"  ✅ Average build time: {ci['average_build_time_minutes']} minutes ({ci['average_build_time_seconds']} seconds)"
                )
                print(f"  Total successful runs: {ci['total_runs']}")
                print(f"  Period: Last {ci['period_days']} days")
            else:
                print(f"  ⚠️  {ci.get('message', 'Not measured')}")
            print()

        # PR Merge Time
        if "pr_merge_time" in metrics:
            pr = metrics["pr_merge_time"]
            print("PR Merge Time:")
            if pr["status"] == "success":
                print(
                    f"  ✅ Average merge time: {pr['average_merge_time_days']} days ({pr['average_merge_time_hours']} hours)"
                )
                print(f"  Total merged PRs: {pr['total_prs']}")
                print(f"  Period: Last {pr['period_days']} days")
            else:
                print(f"  ⚠️  {pr.get('message', 'Not measured')}")
            print()

        # Bug Escape Rate
        if "bug_escape_rate" in metrics:
            bugs = metrics["bug_escape_rate"]
            print("Bug Escape Rate:")
            if bugs["status"] == "success":
                print(f"  ✅ Bug escape rate: {bugs['bug_escape_rate_percent']}%")
                print(f"  Total bugs: {bugs['total_bugs']}")
                print(f"  Bugs found in production: {bugs['bugs_found_in_production']}")
                print(
                    f"  Bugs found before production: {bugs['bugs_found_before_production']}"
                )
                print(f"  Period: Last {bugs['period_days']} days")
                if "note" in bugs:
                    print(f"  Note: {bugs['note']}")
            else:
                print(f"  ⚠️  {bugs.get('message', 'Not measured')}")
            print()

        print("=" * 60)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Measure development metrics for the repository"
    )
    parser.add_argument(
        "--ci-only",
        action="store_true",
        help="Measure CI/CD build time only",
    )
    parser.add_argument(
        "--pr-only",
        action="store_true",
        help="Measure PR merge time only",
    )
    parser.add_argument(
        "--bugs-only",
        action="store_true",
        help="Measure bug escape rate only",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )

    args = parser.parse_args()

    try:
        owner, repo = get_repo_info()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    metrics: dict[str, Any] = {}

    # Measure CI/CD build time
    if not args.pr_only and not args.bugs_only:
        try:
            metrics["ci_build_time"] = measure_ci_build_time(owner, repo, args.days)
        except Exception as e:
            metrics["ci_build_time"] = {
                "status": "error",
                "message": str(e),
            }

    # Measure PR merge time
    if not args.ci_only and not args.bugs_only:
        try:
            metrics["pr_merge_time"] = measure_pr_merge_time(
                owner, repo, args.days * 3
            )  # Look back 3x for PRs
        except Exception as e:
            metrics["pr_merge_time"] = {
                "status": "error",
                "message": str(e),
            }

    # Measure bug escape rate
    if not args.ci_only and not args.pr_only:
        try:
            metrics["bug_escape_rate"] = measure_bug_escape_rate(
                owner, repo, args.days * 3
            )  # Look back 3x for bugs
        except Exception as e:
            metrics["bug_escape_rate"] = {
                "status": "error",
                "message": str(e),
            }

    format_output(metrics, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
