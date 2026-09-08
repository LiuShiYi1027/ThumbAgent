/**
 * Generated from contracts/schemas/skill-dsl.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface ToolStep {
  type: "tool";
  step_id: string;
  tool_id: string;
  arguments: Record<string, unknown>;
}

export interface SkillStep {
  type: "skill";
  step_id: string;
  skill_id: string;
  arguments: Record<string, unknown>;
}

export interface LoopStep {
  type: "loop";
  step_id: string;
  max_duration_seconds: number;
  max_iterations: number;
  steps: Array<ToolStep | SkillStep>;
}

export interface IfStep {
  type: "if";
  step_id: string;
  condition: {
    step: string;
    field: "status";
    equals: "succeeded" | "failed";
  };
  then: Array<ToolStep | SkillStep>;
  else?: Array<ToolStep | SkillStep>;
}

export interface SkillDsl {
  schema_version: "1.0.0";
  skill_id: string;
  skill_version: string;
  name: string;
  description: string;
  timeout_seconds?: number;
  inputs: Array<{
    name: string;
    type: "string" | "integer" | "number" | "boolean";
    required?: boolean;
    description?: string;
    max_length?: number;
    minimum?: number;
    maximum?: number;
  }>;
  steps: Array<ToolStep | SkillStep | LoopStep | IfStep>;
}
