/**
 * Generated from contracts/schemas/app-removal-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AppInspectionResult } from "./app-inspection-result";

export interface AppRemovalResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "app.uninstall";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  removed_app: AppInspectionResult;
  data_retained: boolean;
  evidence_refs: unknown[];
  started_at: string;
  completed_at: string;
}
