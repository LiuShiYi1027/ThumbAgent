/**
 * Generated from contracts/schemas/app-runtime-state.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AppInspectionResult } from "./app-inspection-result";

export interface AppRuntimeState {
  schema_version: "1.0.0";
  device_id: string;
  app: AppInspectionResult;
  process_present: boolean;
  foreground: boolean;
  stopped: boolean | null;
  observed_at: string;
}
