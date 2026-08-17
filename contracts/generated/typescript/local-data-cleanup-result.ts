/**
 * Generated from contracts/schemas/local-data-cleanup-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface LocalDataCleanupResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "local.data.cleanup";
  skill_version: "1.0.0";
  success: true;
  status: "succeeded";
  verification: "artifacts_absent";
  retention_days: number;
  cutoff_at: string;
  deleted_count: number;
  deleted_bytes: number;
  deleted_artifact_ids: string[];
  evidence_refs: unknown[];
  started_at: string;
  completed_at: string;
}
