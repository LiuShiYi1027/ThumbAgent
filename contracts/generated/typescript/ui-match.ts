/**
 * Generated from contracts/schemas/ui-match.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { UiNode } from "./ui-node";
import type { UiSelector } from "./ui-selector";

export interface UiMatch {
  schema_version: "1.0.0";
  selector: UiSelector;
  matched_node: UiNode;
  target_node: UiNode;
  tap_x: number;
  tap_y: number;
}
