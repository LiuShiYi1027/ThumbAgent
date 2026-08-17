/**
 * Generated from contracts/schemas/device-performance-snapshot.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface DevicePerformanceSnapshot {
  schema_version: "1.0.0";
  snapshot_id: string;
  device_id: string;
  captured_at: string;
  cpu: {
    total_usage_percent: number;
  };
  memory: {
    total_bytes: number;
    free_bytes: number;
    used_percent: number;
  };
  battery: {
    level_percent: number;
    temperature_celsius: number | null;
    status: "unknown" | "charging" | "discharging" | "not_charging" | "full";
    plugged: "none" | "ac" | "usb" | "wireless" | "dock" | "unknown";
  };
  system: {
    uptime_seconds: number;
    load_average_1m: number;
    load_average_5m: number;
    load_average_15m: number;
  };
}
