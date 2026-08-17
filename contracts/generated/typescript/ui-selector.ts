/**
 * Generated from contracts/schemas/ui-selector.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface UiSelector {
  strategy: "resource_id" | "text" | "content_description";
  value: string;
  match?: "exact" | "contains";
  clickable?: boolean;
  enabled?: boolean;
  resolve_clickable_ancestor?: boolean;
  package?: string;
  ancestor_path?: Array<{
    strategy: "resource_id" | "text" | "content_description";
    value: string;
    match?: "exact" | "contains";
  }>;
}
