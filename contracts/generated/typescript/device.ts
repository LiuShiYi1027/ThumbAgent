/**
 * Generated from contracts/schemas/device.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

/** A mobile device visible to the Mobile Agent runtime. */
export interface Device {
  schema_version: "1.0.0";
  device_id: string;
  platform: "android" | "ios" | "harmonyos";
  name: string;
  model: string;
  os_version: string;
  connection: "online" | "offline" | "unauthorized" | "unknown";
  session_id: string | null;
  capabilities: string[];
}
