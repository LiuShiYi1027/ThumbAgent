/**
 * Generated from contracts/schemas/app-lifecycle-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AppInspectionResult } from "./app-inspection-result";
import type { AppRuntimeState } from "./app-runtime-state";

export interface AppLifecycleResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "app.open" | "app.stop" | "app.data.clear";
  skill_version: "1.0.0";
  device_id: string;
  operation: "launch" | "stop" | "clear_data";
  success: true;
  status: "succeeded";
  verification: "verified";
  app: AppInspectionResult;
  state: AppRuntimeState;
  data_cleared: boolean | null;
  evidence_refs: unknown[];
  started_at: string;
  completed_at: string;
}
