import contextlib
import io
import unittest
from unittest.mock import patch

import verify


HEAD = "a" * 40
APP_ID = 4602759
TITLE_POLICY = "ci-toolkit/pull-request-title"
PR_UPDATED_AT = "2026-10-21T18:00:00Z"
PR_TITLE = "test: exercise the fixture"
TITLE_SUMMARY = ("✅ **PR title is a conventional release commit header.**\n\n"
                 "| Squash commit title | Result |\n|---|---|\n"
                 "| `test: exercise the fixture` | ✅ |")


def check(name, **changes):
    return {"id": 1, "name": name, "head_sha": HEAD, "app": {"id": APP_ID},
            "status": "completed", "conclusion": "success",
            "completed_at": "2026-10-21T18:00:01Z",
            "output": {"summary": TITLE_SUMMARY} if name == TITLE_POLICY else None, **changes}


class BadgeFixtureVerification(unittest.TestCase):
    def problems(self, extras=(), omitted=(), workflow_conclusion="success", title=PR_TITLE):
        runs = [check(name) for name in verify.EXPECTED | {TITLE_POLICY} if name not in omitted]
        workflow = {"id": 1, "head_sha": HEAD, "status": "completed",
                    "conclusion": workflow_conclusion}
        with patch.object(verify, "check_runs", return_value=runs + list(extras)), \
                patch.object(verify, "fixture_run", return_value=workflow):
            return verify.incomplete("pawelchcki/runnerless-integration-tests", HEAD, APP_ID, False, title)

    def test_staging_and_title_policy_without_badge_checks_pass(self):
        self.assertEqual(self.problems(), [])

    def test_native_title_policy_check_is_required(self):
        self.assertTrue(any(TITLE_POLICY in problem for problem in
                            self.problems(omitted=[TITLE_POLICY])))

    def test_native_title_policy_requires_success_on_the_head_from_the_expected_app(self):
        for changes in [{"app": {"id": 1}}, {"head_sha": "b" * 40},
                        {"status": "in_progress", "conclusion": None},
                        {"conclusion": "failure"}, {"conclusion": "skipped"}]:
            with self.subTest(changes=changes):
                self.assertTrue(any(TITLE_POLICY in problem for problem in self.problems(
                    [check(TITLE_POLICY, **changes)], omitted=[TITLE_POLICY])))

    def test_latest_owned_title_policy_attempt_must_succeed(self):
        self.assertTrue(any(TITLE_POLICY in problem for problem in self.problems(
            [check(TITLE_POLICY, id=2, conclusion="failure")])))

    def test_successful_owned_badge_checks_are_optional(self):
        self.assertEqual(self.problems([check(name) for name in (
            "Runnerless", "Runnerless configuration", "Runnerless / Program configuration")]), [])

    def test_other_production_effects_are_rejected(self):
        self.assertIn("unexpected production", self.problems([check("Runnerless / Deploy")])[0])

    def test_other_native_policy_effects_are_rejected(self):
        self.assertTrue(any("unexpected production" in problem for problem in
                            self.problems([check("ci-toolkit/another-policy")])))

    def test_successful_title_attempt_supersedes_an_older_failure(self):
        self.assertEqual(self.problems([check(TITLE_POLICY, id=0, conclusion="failure")]), [])

    def test_matching_title_witness_accepts_reused_check_timestamps(self):
        for completed_at in ["2026-10-21T17:59:59Z", PR_UPDATED_AT, None, "invalid"]:
            with self.subTest(completed_at=completed_at):
                self.assertEqual(self.problems(
                    [check(TITLE_POLICY, created_at="2026-10-21T17:00:00Z",
                           started_at="2026-10-21T17:00:00Z", completed_at=completed_at)],
                    omitted=[TITLE_POLICY]), [])

    def test_previous_title_evaluation_finishing_after_an_edit_is_rejected(self):
        summary = ("✅ **PR title is a conventional release commit header.**\n\n"
                   "| Squash commit title | Result |\n|---|---|\n"
                   "| `test: the previous title` | ✅ |")
        self.assertTrue(any(TITLE_POLICY in problem for problem in self.problems(
            [check(TITLE_POLICY, started_at="2026-10-21T17:59:59Z",
                   completed_at="2026-10-21T18:00:01Z", output={"summary": summary})],
            omitted=[TITLE_POLICY])))

    def test_title_witness_requires_the_complete_native_summary(self):
        for output in [None, {}, {"summary": None}, {"summary": "success"},
                       {"summary": "unrecognized format\n| `test: exercise the fixture` | ✅ |"},
                       {"summary": TITLE_SUMMARY + "\n\nEvaluated 2 open PRs sharing this head."}]:
            with self.subTest(output=output):
                self.assertTrue(any(TITLE_POLICY in problem for problem in self.problems(
                    [check(TITLE_POLICY, output=output)], omitted=[TITLE_POLICY])))

    def test_title_witness_matches_native_backtick_and_pipe_escaping(self):
        title = r"test: use `pipes|ticks` and a \backslash"
        summary = ("✅ **PR title is a conventional release commit header.**\n\n"
                   "| Squash commit title | Result |\n|---|---|\n"
                   r"| `test: use \`pipes\|ticks\` and a \backslash` | ✅ |")
        self.assertEqual(self.problems(
            [check(TITLE_POLICY, output={"summary": summary})], omitted=[TITLE_POLICY], title=title), [])

    def test_title_witness_bound_counts_utf16_units(self):
        for title in ["test: " + "x" * 250, "test: " + "😀" * 125]:
            summary = ("✅ **PR title is a conventional release commit header.**\n\n"
                       "| Squash commit title | Result |\n|---|---|\n"
                       f"| `{title}` | ✅ |")
            with self.subTest(title=title):
                self.assertEqual(self.problems(
                    [check(TITLE_POLICY, output={"summary": summary})], omitted=[TITLE_POLICY], title=title), [])
                self.assertTrue(any(TITLE_POLICY in problem for problem in self.problems(
                    [check(TITLE_POLICY, output={"summary": summary})], omitted=[TITLE_POLICY], title=title + "x")))

    def test_title_witness_rejects_a_truncated_title(self):
        title = "test: " + "😀" * 126
        truncated = "test: " + "😀" * 125
        summary = ("✅ **PR title is a conventional release commit header.**\n\n"
                   "| Squash commit title | Result |\n|---|---|\n"
                   f"| `{truncated}` | ✅ |")
        self.assertTrue(any(TITLE_POLICY in problem for problem in self.problems(
            [check(TITLE_POLICY, output={"summary": summary})], omitted=[TITLE_POLICY], title=title)))

    def test_badge_check_identity_and_completion_are_required(self):
        for name in ("Runnerless", "Runnerless configuration", "Runnerless / Program configuration"):
            for changes in [{"app": {"id": 1}}, {"head_sha": "b" * 40},
                            {"status": "in_progress", "conclusion": None}, {"conclusion": "failure"}]:
                with self.subTest(name=name, changes=changes):
                    self.assertIn("badge checks are not successful", self.problems([check(name, **changes)])[0])

    def test_badge_cannot_replace_a_missing_staging_check(self):
        self.assertTrue(any("missing checks" in problem for problem in self.problems(
            [check("Runnerless")], omitted=[verify.STAGING_AGGREGATE])))

    def test_badge_cannot_hide_a_failed_fixture_workflow(self):
        self.assertTrue(any("fixture workflow concluded" in problem for problem in self.problems(
            [check("Runnerless")], workflow_conclusion="failure")))


class SnapshotVerification(unittest.TestCase):
    def result(self, snapshots):
        args = ["verify.py", "--repo", "pawelchcki/runnerless-integration-tests",
                "--pr", "1", "--app-id", str(APP_ID)]
        with patch.object(verify.sys, "argv", args), \
                patch.object(verify, "current_pr", side_effect=[{"updated_at": PR_UPDATED_AT, **item} for item in snapshots]), \
                patch.object(verify, "incomplete", return_value=[]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return verify.main()

    def test_unchanged_snapshot_passes(self):
        initial = {"head": {"sha": HEAD}, "title": "test: exercise the fixture"}
        self.assertEqual(self.result([initial, initial, initial]), 0)

    def test_title_change_during_check_reads_is_rejected(self):
        initial = {"head": {"sha": HEAD}, "title": "test: exercise the fixture"}
        changed = {"head": {"sha": HEAD}, "title": "invalid title"}
        self.assertEqual(self.result([initial, initial, changed]), 2)

    def test_title_change_before_polling_is_rejected(self):
        initial = {"head": {"sha": HEAD}, "title": "test: exercise the fixture"}
        changed = {"head": {"sha": HEAD}, "title": "invalid title"}
        self.assertEqual(self.result([initial, changed, changed]), 2)

    def test_head_change_during_check_reads_is_rejected(self):
        initial = {"head": {"sha": HEAD}, "title": "test: exercise the fixture"}
        changed = {"head": {"sha": "b" * 40}, "title": initial["title"]}
        self.assertEqual(self.result([initial, initial, changed]), 2)

    def test_revision_change_during_check_reads_is_rejected(self):
        initial = {"head": {"sha": HEAD}, "title": "test: exercise the fixture"}
        changed = {**initial, "updated_at": "2026-10-21T18:00:02Z"}
        self.assertEqual(self.result([initial, initial, changed]), 2)


if __name__ == "__main__":
    unittest.main()
