#!/usr/bin/env python3
"""Read-only verifier for production title policy and one Runnerless staging-fixture PR."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import re
from typing import Any

STAGING_AGGREGATE = "Runnerless / [staging]"
STAGING_CONFIGURATION = "Runnerless / [staging] Program configuration"
FIXTURE_WORKFLOW = "Runnerless fixture"
TITLE_POLICY = "ci-toolkit/pull-request-title"
TITLE_WITNESS_UNITS = 256
BADGE_CHECKS = {"Runnerless", "Runnerless configuration", "Runnerless / Program configuration"}
# The llm-cc content scan verdict, published once every changed file is scored. Scoring is
# asynchronous, so the verdict is required: success before it appears would hide a failed scan.
SCAN_CHECK = "Runnerless / LM-CC/token"
PROGRAM_CHECKS = BADGE_CHECKS | {SCAN_CHECK}
EXPECTED = {
    STAGING_AGGREGATE,
    "Runnerless / [staging] Fixture pull request",
    "Runnerless / [staging] Fixture workflow run",
    "Runnerless / [staging] Fixture check run",
    "Runnerless / [staging] Fixture check suite",
}


# owner/name, as GitHub spells repository full names (owner and repository segments).
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def gh_json(path: str) -> Any:
    result = subprocess.run(["gh", "api", path], check=False, capture_output=True, text=True, timeout=20)
    if result.returncode:
        # GitHub response text can contain repository-controlled values. Do not echo it.
        raise RuntimeError(f"gh api failed for {path} (exit {result.returncode})")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"gh api returned invalid JSON for {path}") from error


def current_pr(repo: str, number: int) -> dict[str, Any]:
    value = gh_json(f"repos/{repo}/pulls/{number}")
    sha = value.get("head", {}).get("sha") if isinstance(value, dict) else None
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise RuntimeError("GitHub did not return a PR head SHA")
    return value


def check_runs(repo: str, sha: str) -> list[dict[str, Any]]:
    value = gh_json(f"repos/{repo}/commits/{sha}/check-runs?filter=all&per_page=100")
    runs = value.get("check_runs") if isinstance(value, dict) else None
    if not isinstance(value, dict) or not isinstance(runs, list) or value.get("total_count") != len(runs) or len(runs) >= 100:
        raise RuntimeError("GitHub did not return check_runs")
    return [run for run in runs if isinstance(run, dict)]


def fixture_run(repo: str, sha: str) -> dict[str, Any] | None:
    value = gh_json(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100")
    runs = value.get("workflow_runs") if isinstance(value, dict) else None
    if not isinstance(value, dict) or not isinstance(runs, list) or value.get("total_count") != len(runs) or len(runs) >= 100:
        raise RuntimeError("GitHub did not return workflow_runs")
    matches = [run for run in runs if isinstance(run, dict) and run.get("name") == FIXTURE_WORKFLOW]
    return max(matches, key=lambda run: int(run.get("id", 0)), default=None)


def title_witness_matches(run: dict[str, Any], title: str) -> bool:
    # Native evaluateTitle() truncates its table cell at 256 JavaScript UTF-16
    # code units. Only its complete, single-PR summary can witness this full title.
    if not isinstance(title, str):
        return False
    try:
        if len(title.encode("utf-16-le")) // 2 > TITLE_WITNESS_UNITS:
            return False
    except UnicodeEncodeError:
        return False
    output = run.get("output")
    if not isinstance(output, dict):
        return False
    escaped = title.replace("`", "\\`").replace("|", "\\|")
    expected = ("✅ **PR title is a conventional release commit header.**\n\n"
                "| Squash commit title | Result |\n|---|---|\n"
                f"| `{escaped}` | ✅ |")
    return output.get("summary") == expected


def incomplete(repo: str, sha: str, app_id: int, require_configuration: bool,
               pr_title: str) -> list[str]:
    runs = check_runs(repo, sha)
    names = {run.get("name") for run in runs if isinstance(run.get("name"), str)}
    production = [run for run in runs if isinstance(run.get("name"), str)
                  and (run["name"] in {"Runnerless", "Runnerless configuration"}
                       or run["name"].startswith("ci-toolkit/")
                       or run["name"].startswith("Runnerless / ") and "[staging]" not in run["name"])]
    unexpected = sorted({run["name"] for run in production} - (PROGRAM_CHECKS | {TITLE_POLICY}))
    if unexpected:
        return ["fixture produced unexpected production Runnerless checks: " + ", ".join(unexpected)]
    # Every badge attempt must succeed. The scan verdict is required below, where only its
    # latest owned attempt counts, so a successful retry supersedes an earlier failure.
    invalid_badge = sorted({run["name"] for run in production
                            if run["name"] in BADGE_CHECKS and
                            (run.get("head_sha") != sha or run.get("app", {}).get("id") != app_id
                             or run.get("status") != "completed" or run.get("conclusion") != "success")})
    if invalid_badge:
        return ["badge checks are not successful App checks on the PR head: " + ", ".join(invalid_badge)]
    needed = EXPECTED | {TITLE_POLICY, SCAN_CHECK}
    if require_configuration:
        needed.add(STAGING_CONFIGURATION)
    missing = sorted(needed - names)
    invalid = []
    for name in sorted(needed & names):
        matches = [run for run in runs if run.get("name") == name]
        owned = [run for run in matches if run.get("head_sha") == sha and run.get("app", {}).get("id") == app_id]
        latest = max(owned, key=lambda run: int(run.get("id", 0)), default=None)
        if (latest is None or latest.get("status") != "completed" or latest.get("conclusion") != "success"
                or name == TITLE_POLICY and not title_witness_matches(latest, pr_title)):
            invalid.append(name)
    aggregate = [run for run in runs if run.get("name") == STAGING_AGGREGATE
                 and run.get("head_sha") == sha and run.get("app", {}).get("id") == app_id]
    if any(run.get("status") != "completed" or run.get("conclusion") != "success" for run in aggregate):
        invalid.append(STAGING_AGGREGATE + " (a delivery failed or is pending)")
    run = fixture_run(repo, sha)
    problems = (["missing checks: " + ", ".join(missing)] if missing else [])
    if invalid:
        problems.append("checks are not successful Runnerless-App checks on the PR head: " + ", ".join(invalid))
    if run is None:
        problems.append("Runnerless fixture workflow has not appeared")
    elif run.get("head_sha") != sha:
        problems.append("Runnerless fixture workflow is for a different commit")
    elif run.get("status") != "completed":
        problems.append("Runnerless fixture workflow is still running")
    elif run.get("conclusion") != "success":
        problems.append(f"Runnerless fixture workflow concluded {run.get('conclusion')!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, metavar="OWNER/REPO")
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--timeout", type=int, default=300, help="maximum polling time in seconds (default: 300)")
    parser.add_argument("--interval", type=int, default=10, help="poll interval in seconds (default: 10)")
    parser.add_argument("--app-id", type=int, required=True, help="numeric GitHub App ID that publishes Runnerless checks")
    parser.add_argument("--require-configuration", action="store_true", help="require the PR-candidate configuration check")
    args = parser.parse_args()
    if not REPOSITORY.fullmatch(args.repo) or args.timeout < 1 or args.interval < 1 or args.pr < 1 or args.app_id < 1:
        parser.error("repo must be OWNER/REPO; pr, app-id, timeout, and interval must be positive")
    initial = current_pr(args.repo, args.pr)
    initial_sha, initial_title, initial_updated = initial["head"]["sha"], initial["title"], initial["updated_at"]
    deadline = time.monotonic() + args.timeout
    while True:
        current = current_pr(args.repo, args.pr)
        current_sha = current["head"]["sha"]
        if (current_sha != initial_sha or current["title"] != initial_title
                or current["updated_at"] != initial_updated):
            print("PR changed while verifying; rerun against the new snapshot.", file=sys.stderr)
            return 2
        problems = incomplete(args.repo, current_sha, args.app_id, args.require_configuration, initial_title)
        if not problems:
            # Title edits can invalidate the native check without changing the head.
            final = current_pr(args.repo, args.pr)
            if (final["head"]["sha"] != current_sha or final["title"] != initial_title
                    or final["updated_at"] != initial_updated):
                print("PR changed while verifying; rerun against the new snapshot.", file=sys.stderr)
                return 2
            print(f"staging fixture verified for {args.repo} PR #{args.pr} at {current_sha}")
            return 0
        if time.monotonic() >= deadline:
            print("verification timed out: " + "; ".join(problems), file=sys.stderr)
            return 1
        time.sleep(min(args.interval, max(0, deadline - time.monotonic())))


if __name__ == "__main__":
    raise SystemExit(main())
