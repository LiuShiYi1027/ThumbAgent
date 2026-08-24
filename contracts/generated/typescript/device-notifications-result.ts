/**
 * Generated from contracts/schemas/device-notifications-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { Artifact } from "./artifact";

export interface DeviceNotificationsResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "device.notifications.read";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  source: "android_notification_service";
  requested_max_notifications: number;
  notifications: Array<{
    package: string;
    title: string | null;
    posted_at: string | null;
  }>;
  total_matched: number;
  truncated: boolean;
  evidence_refs: string[];
  artifact: Artifact;
  started_at: string;
  completed_at: string;
}
