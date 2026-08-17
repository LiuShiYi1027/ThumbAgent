/**
 * Generated from contracts/schemas/device-log-capture-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { Artifact } from "./artifact";

export interface DeviceLogCaptureResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "device.logs.collect";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  source: "android_logcat";
  minimum_level: "verbose" | "debug" | "info" | "warn" | "error" | "fatal";
  requested_max_lines: number;
  captured_bytes: number;
  truncated: boolean;
  redaction_count: number;
  evidence_refs: string[];
  artifact: Artifact;
  started_at: string;
  completed_at: string;
}
