/**
 * Generated from contracts/schemas/action-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { Observation } from "./observation";
import type { UiMatch } from "./ui-match";

export interface ActionResult {
  schema_version: "1.0.0";
  action_id: string;
  tool_id: "app.launch" | "navigation.back" | "navigation.home" | "input.tap" | "input.tap_element" | "input.swipe" | "input.text";
  device_id: string;
  status: "succeeded" | "failed" | "unknown_outcome" | "rejected";
  verification: "verified" | "not_verified" | "inconclusive";
  started_at: string;
  completed_at: string;
  before: Observation;
  after: Observation;
  ui_match?: UiMatch | null;
}
