/**
 * Generated from contracts/schemas/agent-decision.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface AgentDecision {
  schema_version: "1.0.0";
  decision_id: string;
  decision_type: "run_skill" | "run_tool" | "finish";
  skill_id: string;
  tool_id: string;
  arguments: Record<string, unknown>;
  reason: string;
  planner_id: string;
  confidence: number | null;
  source: "planner" | "rule" | "llm";
  repair_count?: number;
  provider_retry_count?: number;
  provider_latency_ms?: number;
  provider_attempt_count?: number;
}
