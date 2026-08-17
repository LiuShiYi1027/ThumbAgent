/**
 * Generated from contracts/schemas/diagnostic-bundle-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AppRuntimeState } from "./app-runtime-state";
import type { Artifact } from "./artifact";

export interface DiagnosticBundleResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "device.diagnostics.bundle";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  app_state: AppRuntimeState | null;
  foreground_app: Record<string, unknown>;
  log_summary: {
    minimum_level: string;
    captured_bytes: number;
    truncated: boolean;
    redaction_count: number;
  };
  performance_summary: Record<string, unknown>;
  source_artifacts: Artifact[];
  bundle_artifact: Artifact;
  evidence_refs: string[];
  started_at: string;
  completed_at: string;
}
