/**
 * Generated from contracts/schemas/runtime-readiness.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { Device } from "./device";

export interface DeviceAvailability {
  device: Device;
  status: "ready" | "busy" | "offline" | "unauthorized" | "unknown";
  lease_owner_id: string | null;
  lease_session_id: string | null;
  lease_expired: boolean | null;
  issues: Issue[];
}

export interface Issue {
  code: string;
  message: string;
  suggested_action: string;
}

export interface RuntimeReadiness {
  schema_version: "1.0.0";
  generated_at: string;
  status: "ready" | "attention" | "blocked";
  gateway: {
    platform: string;
    transport: string;
    status: "available" | "unavailable";
    issue: Issue | null;
  };
  devices: DeviceAvailability[];
  summary: {
    total: number;
    ready: number;
    busy: number;
    attention: number;
  };
  issues: Issue[];
}
