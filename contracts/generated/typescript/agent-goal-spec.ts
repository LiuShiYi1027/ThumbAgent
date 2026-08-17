/**
 * Generated from contracts/schemas/agent-goal-spec.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AgentGoalAcceptance } from "./agent-goal-acceptance";

export interface AgentGoalSpec {
  schema_version: "1.0.0";
  source_goal: string;
  execution_goal: string;
  acceptance?: AgentGoalAcceptance;
  assumptions: string[];
  confidence: number;
  compiler_id: string;
  source: "rule" | "llm";
  confirmation_required: boolean;
}
