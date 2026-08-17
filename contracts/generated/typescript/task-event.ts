/**
 * Generated from contracts/schemas/task-event.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface TaskEvent {
  schema_version: "1.0.0";
  event_id: string;
  task_id: string;
  device_id: string;
  sequence: number;
  event_type: "task.queued" | "task.started" | "task.step_completed" | "task.cancel_requested" | "task.completed";
  occurred_at: string;
  payload: Record<string, unknown>;
}
