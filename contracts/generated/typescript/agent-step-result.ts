/**
 * Generated from contracts/schemas/agent-step-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { ActionResult } from "./action-result";
import type { AgentActionFeedback } from "./agent-action-feedback";
import type { AgentDecision } from "./agent-decision";
import type { AgentObservationSummary } from "./agent-observation-summary";
import type { NavigationResult } from "./navigation-result";
import type { UiNode } from "./ui-node";

export interface AgentStepResult {
  schema_version: "1.0.0";
  round: number;
  observation: AgentObservationSummary;
  decision: AgentDecision;
  action_feedback?: AgentActionFeedback | null;
  action_result: ActionResult | null;
  skill_result: NavigationResult | null;
  verified_node: UiNode | null;
}
