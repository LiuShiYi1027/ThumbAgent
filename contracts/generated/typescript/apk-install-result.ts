/**
 * Generated from contracts/schemas/apk-install-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AppInspectionResult } from "./app-inspection-result";

export interface ApkInstallResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "app.install";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  app: AppInspectionResult;
  apk_sha256: string;
  apk_size_bytes: number;
  replaced_existing: boolean;
  evidence_refs: unknown[];
  started_at: string;
  completed_at: string;
}
