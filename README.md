# Runnerless integration tests

[![Runnerless CI: slowest job](https://badges.runnerlesshq.com/github.com/pawelchcki/runnerless-integration-tests/badge.svg)](https://app.runnerlesshq.com)

Public fixtures for testing the Runnerless-managed staging instance and GitHub Actions webhook routing. The repository is owned by `pawelchcki`, has repository ID `1383104537`, and has $0 fixed monthly idle cost. GitHub-hosted public-repository workflow usage is free within GitHub's public repository allowance.

## What runs

- `.runnerless-ci.ts` defines the public medium CI badge; its `run` function has no effects.
- `.runnerless-ci.staging.ts` is the trusted staging program. It reports receipt of pull request, workflow run, check run, check suite, and commit status events.
- `.github/workflows/fixture.yml` runs a deterministic job on pull requests using a standard GitHub-hosted Linux runner, no actions, no checkout, and `permissions: {}`.
- `input.txt` is the disposable PR input.
- `verify.py` checks the current PR revision, Runnerless App identity, successful staging checks, and successful Actions workflow. It permits only the production badge program’s aggregate/configuration checks, verifies their App identity and commit, and rejects unexpected production checks and incomplete API responses.

No repository secrets or deployment credentials are needed.

## Activation

The fixture is published; staging execution is not yet activated or verified live.

The existing My Toolkit GitHub App must have access to this repository and subscribe to pull request, workflow run, check run, check suite, and commit status events. Its access has not yet been verified with an App credential. After access is confirmed, the operator requests the shared long-lived `staging` instance from production Runnerless. Runnerless dispatches its locked default-branch lifecycle workflow in `pawelchcki/my-infra`, provisions isolated D1/R2/queues and a Custom Domain, deploys the child, and enables routing only after signed registration and a live probe. No route-map JSON or per-child service binding is added here. The production `.runnerless-ci.ts` is reserved for the public badge. Keep fixture assertions in `.runnerless-ci.staging.ts`.

## Exercise the integration

1. Open a PR changing only `input.txt`, with `main` as its base. Runnerless executes the staging program from the pinned base commit; a changed PR-head program receives configuration validation only.
2. Wait for the `Runnerless fixture` workflow to succeed.
3. From this repository's checkout, with Python 3.10+ and an authenticated GitHub CLI, run:

```sh
python3 verify.py --repo pawelchcki/runnerless-integration-tests --pr 1 --app-id 4602759
```

Replace `1` with the actual PR number. The verifier waits up to five minutes and fails if the PR head changes. Expected checks are `Runnerless / [staging]` and the namespaced `Fixture pull request`, `Fixture workflow run`, `Fixture check run`, and `Fixture check suite` checks. Commit status coverage is optional and requires an external status producer.

4. Push another data-only commit to exercise the same cached program, then run the verifier again. Cache reuse itself requires the operator's compiler metrics; GitHub checks alone do not prove a cache hit.
5. To test candidate configuration validation, make a harmless program comment change in the PR and add `--require-configuration` to the verifier command.
6. Close the test PR and delete its disposable branch after collecting the results. Staging stays shared and long lived; any later PR preview is disabled immediately on close and its isolated resources expire after seven days.

Remove only this repository from any shared App's selected-repository list when retiring the fixture. Do not uninstall the shared App from the account.

## Validation status

The program and verifier have local compilation/unit-test coverage in the infrastructure source repository. Publishing this fixture does not establish that a live staging instance exists or that a live end-to-end run passed.
