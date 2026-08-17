/**
 * Generated from contracts/schemas/skill-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { ActionResult } from "./action-result";

export interface SkillResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "app.open";
  skill_version: "1.0.0";
  success: boolean;
  status: "succeeded" | "failed" | "unknown_outcome" | "rejected";
  started_at: string;
  completed_at: string;
  action: ActionResult;
}
