import { configuration } from "runnerless/v1";
import { badges, BadgeSpec, scans, ScanSpec } from "runnerless/v1";

// LM-CC complexity scored by the organization's installed llm-cc scanners (ADR 0027);
// ratcheted, so a pull request may not raise LM-CC per token.
const complexity = new ScanSpec("complexity", "llm-cc", true);

// Production title policy, CI badge and content scan. Staging fixture checks stay in
// .runnerless-ci.staging.ts.
export function configure(): void {
  configuration.titlePolicy();
  badges.define(new BadgeSpec("badge", "medium", "slowest-job"));
  scans.define(complexity);
}

export function run(): void {
  scans.publish(complexity, "LM-CC/token");
}
