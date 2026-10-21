import unittest
from unittest.mock import patch

import verify


HEAD = "a" * 40
APP_ID = 4602759
TITLE_POLICY = "ci-toolkit/pull-request-title"


def check(name, **changes):
    return {"id": 1, "name": name, "head_sha": HEAD, "app": {"id": APP_ID},
            "status": "completed", "conclusion": "success", **changes}


class BadgeFixtureVerification(unittest.TestCase):
    def problems(self, extras=(), omitted=(), workflow_conclusion="success"):
        runs = [check(name) for name in verify.EXPECTED | {TITLE_POLICY} if name not in omitted]
        workflow = {"id": 1, "head_sha": HEAD, "status": "completed",
                    "conclusion": workflow_conclusion}
        with patch.object(verify, "check_runs", return_value=runs + list(extras)), \
                patch.object(verify, "fixture_run", return_value=workflow):
            return verify.incomplete("pawelchcki/runnerless-integration-tests", HEAD, APP_ID, False)

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


if __name__ == "__main__":
    unittest.main()
