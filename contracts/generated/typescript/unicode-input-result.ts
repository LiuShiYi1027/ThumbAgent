/**
 * Generated from contracts/schemas/unicode-input-result.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface UnicodeInputResult {
  schema_version: "1.0.0";
  skill_call_id: string;
  skill_id: "input.unicode_text";
  skill_version: "1.0.0";
  device_id: string;
  success: true;
  status: "succeeded";
  verification: "verified";
  field: {
    selector: {
      strategy: string;
      value: string;
      match: string;
    };
    package: string;
    resource_id?: string;
  };
  text_length: number;
  text_sha256: string;
  ime: {
    helper_id: string;
    previous_id: string;
    restored: true;
  };
  evidence_refs: string[];
  started_at: string;
  completed_at: string;
}
