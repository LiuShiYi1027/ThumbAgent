/**
 * Generated from contracts/schemas/observation.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { Artifact } from "./artifact";

export interface Observation {
  schema_version: "1.0.0";
  observation_id: string;
  device_id: string;
  captured_at: string;
  foreground_app: {
    app_id: string;
    activity: string;
    captured_at: string;
  };
  screen: {
    width: number;
    height: number;
    orientation: "portrait" | "landscape" | "square";
    captured_at: string;
    screenshot: Artifact;
  };
  ui_tree: {
    captured_at: string;
    artifact: Artifact;
  };
  device_state: "interactive" | "locked" | "unknown";
}
