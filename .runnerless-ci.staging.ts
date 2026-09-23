// Staging-only Runnerless program for the public integration repository.
//
// This file must be present on the default branch before a pull request is opened:
// Runnerless deliberately loads the trusted program from the pull request base, then
// validates a candidate copy from the head without executing that candidate.
import { configuration, checks, event } from "runnerless";

export function configure(): void {
  configuration.workflow("fixture-routing", ["pull_request", "workflow_run", "check_run", "check_suite", "status"]);
}

export function run(): void {
  const kind = event.get("event");
  if (kind == "pull_request") {
    checks.report("Fixture pull request", true, "Observed a pull_request delivery.");
  } else if (kind == "workflow_run") {
    checks.report("Fixture workflow run", true, "Observed the fixture GitHub Actions workflow_run delivery.");
  } else if (kind == "check_run") {
    checks.report("Fixture check run", true, "Observed a check_run delivery.");
  } else if (kind == "check_suite") {
    checks.report("Fixture check suite", true, "Observed a check_suite delivery.");
  } else if (kind == "status") {
    checks.report("Fixture status", true, "Observed a commit status delivery.");
  }
}
