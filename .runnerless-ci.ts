import { badges, BadgeSpec } from "runnerless/v1";

// Public CI badge only. Staging fixture checks stay in .runnerless-ci.staging.ts.
export function configure(): void {
  badges.define(new BadgeSpec("badge", "medium", "slowest-job"));
}

export function run(): void {}
