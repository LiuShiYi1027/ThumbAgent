/**
 * Generated from contracts/schemas/app-inspection-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface AppInspectionResult {
  app_id: string;
  version_name: string | null;
  version_code: number | null;
  installer_app_id: string | null;
  enabled: boolean | null;
  system_app?: boolean | null;
}
