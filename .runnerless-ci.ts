import { configuration } from "runnerless/v1";
import { badges, BadgeSpec } from "runnerless/v1";

// Production title policy and CI badge. Staging fixture checks stay in .runnerless-ci.staging.ts.
export function configure(): void {
  configuration.titlePolicy();
  badges.define(new BadgeSpec("badge", "medium", "slowest-job"));
}

export function run(): void {}
