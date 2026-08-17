/**
 * Generated from contracts/schemas/navigation-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { ActionResult } from "./action-result";
import type { Observation } from "./observation";
import type { SkillResult } from "./skill-result";
import type { UiNode } from "./ui-node";

export interface NavigationResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "settings.navigate" | "settings.scroll_navigate";
  skill_version: "1.0.0";
  success: true;
  started_at: string;
  completed_at: string;
  open_app: SkillResult;
  tap_action: ActionResult;
  verified_observation: Observation;
  verified_node: UiNode;
}
