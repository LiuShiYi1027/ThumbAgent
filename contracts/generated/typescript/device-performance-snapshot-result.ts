/**
 * Generated from contracts/schemas/device-performance-snapshot-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { Artifact } from "./artifact";
import type { DevicePerformanceSnapshot } from "./device-performance-snapshot";

export interface DevicePerformanceSnapshotResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "device.performance.snapshot";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  snapshot: DevicePerformanceSnapshot;
  evidence_refs: string[];
  artifact: Artifact;
  started_at: string;
  completed_at: string;
}
