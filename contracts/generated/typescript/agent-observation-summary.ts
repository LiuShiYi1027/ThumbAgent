/**
 * Generated from contracts/schemas/agent-observation-summary.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AgentActionFeedback } from "./agent-action-feedback";

export interface AgentObservationSummary {
  schema_version: "1.0.0";
  observation_id: string;
  foreground_app: {
    app_id: string;
    activity: string;
    captured_at: string;
  };
  device_state: "interactive" | "locked" | "unknown";
  ui_summary_total_candidates?: number;
  ui_summary_truncated?: boolean;
  last_action_feedback?: AgentActionFeedback | null;
  ui_summary: Array<{
    text: string;
    content_description: string;
    resource_id: string;
    class_name: string;
    clickable: boolean;
    clickable_ancestor?: boolean;
    enabled: boolean;
  }>;
}
