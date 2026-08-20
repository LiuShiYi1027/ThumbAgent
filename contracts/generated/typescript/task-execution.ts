/**
 * Generated from contracts/schemas/task-execution.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */

export interface TaskExecution {
  schema_version: "1.0.0";
  task_id: string;
  task_type: "agent.run" | "device.logs.collect" | "device.performance.snapshot" | "device.diagnostics.bundle" | "app.install" | "app.uninstall" | "app.launch" | "app.stop" | "app.data.clear" | "local.data.cleanup";
  device_id: string;
  device_session_id: string | null;
  goal: string;
  status: "queued" | "running" | "paused" | "cancelling" | "succeeded" | "failed" | "cancelled" | "timed_out";
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
  deadline_seconds: number;
  deadline_at: string | null;
  cancel_requested: boolean;
  pause_requested: boolean;
  result_available: boolean;
  error: Record<string, unknown> | null;
}
