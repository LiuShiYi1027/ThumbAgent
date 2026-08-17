/**
 * Generated from contracts/schemas/ui-node.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface UiNode {
  schema_version: "1.0.0";
  node_id: string;
  parent_id: string | null;
  depth: number;
  text: string;
  resource_id: string;
  content_description: string;
  class_name: string;
  package: string;
  clickable: boolean;
  enabled: boolean;
  visible: boolean;
  bounds: {
    left: number;
    top: number;
    right: number;
    bottom: number;
  };
}
