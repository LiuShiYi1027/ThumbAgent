/**
 * Generated from contracts/schemas/app-navigation-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface AppNavigationResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "app.navigate";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  target: "settings.home" | "settings.wifi" | "settings.bluetooth" | "settings.wireless" | "settings.display" | "settings.sound" | "settings.storage" | "settings.apps" | "settings.security" | "settings.location" | "settings.date" | "settings.language" | "settings.accessibility" | "settings.about";
  label: string;
  foreground_app: {
    app_id: string;
    activity: string;
  };
  evidence_refs: string[];
  started_at: string;
  completed_at: string;
}
