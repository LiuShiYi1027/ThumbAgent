/**
 * Generated from contracts/schemas/agent-goal-acceptance.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { UiSelector } from "./ui-selector";

export interface AgentGoalAcceptance {
  foreground_app_id?: string;
  foreground_activity?: string;
  expected_selector?: UiSelector;
}
