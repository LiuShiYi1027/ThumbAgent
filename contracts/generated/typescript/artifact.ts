/**
 * Generated from contracts/schemas/artifact.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface Artifact {
  schema_version: "1.0.0";
  artifact_id: string;
  kind: "screenshot" | "ui_tree" | "device_log" | "device_performance" | "diagnostic_bundle";
  content_type: "image/png" | "application/xml" | "text/plain" | "application/json" | "application/zip";
  relative_path: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  availability?: "available" | "expired" | "missing";
}
