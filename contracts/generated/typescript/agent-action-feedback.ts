/**
 * Generated from contracts/schemas/agent-action-feedback.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface AgentActionFeedback {
  schema_version: "1.0.0";
  tool_id: string;
  arguments: Record<string, unknown>;
  effect: "changed" | "unchanged" | "unknown";
  basis: "ui_tree_and_foreground" | "pre_dispatch_validation" | "finish_verification" | "runtime_acceptance" | "not_evaluated";
  message: string;
  error_code?: string;
  details?: Record<string, unknown>;
}
