/**
 * Generated from contracts/schemas/task-run.schema.json by
 * scripts/generate_ts_contracts.py. Do not edit manually;
 * run `make contracts` and commit the result.
 */
import type { AgentGoalAcceptance } from "./agent-goal-acceptance";
import type { AgentGoalSpec } from "./agent-goal-spec";
import type { AgentStepResult } from "./agent-step-result";
import type { ApkInstallResult } from "./apk-install-result";
import type { AppLifecycleResult } from "./app-lifecycle-result";
import type { AppRemovalResult } from "./app-removal-result";
import type { DeviceLogCaptureResult } from "./device-log-capture-result";
import type { DevicePerformanceSnapshotResult } from "./device-performance-snapshot-result";
import type { DiagnosticBundleResult } from "./diagnostic-bundle-result";
import type { LocalDataCleanupResult } from "./local-data-cleanup-result";
import type { NavigationResult } from "./navigation-result";

export interface TaskRun {
  schema_version: "1.0.0";
  task_id: string;
  task_type: "settings.scroll_navigate" | "agent.run" | "device.logs.collect" | "device.performance.snapshot" | "device.diagnostics.bundle" | "app.install" | "app.uninstall" | "app.launch" | "app.stop" | "app.data.clear" | "local.data.cleanup";
  device_id: string;
  device_session_id?: string;
  goal: string;
  goal_spec?: AgentGoalSpec;
  goal_acceptance?: AgentGoalAcceptance;
  completion_source?: "planner_finish" | "runtime_acceptance" | "skill_result";
  status: "succeeded" | "failed" | "cancelled" | "timed_out";
  deadline_seconds?: number;
  started_at: string;
  completed_at: string;
  steps: Array<{
    step_id: string;
    sequence: number;
    kind: "skill" | "agent_round" | "diagnostic";
    name: "settings.scroll_navigate" | "agent.round" | "device.logs.collect" | "device.performance.snapshot" | "device.diagnostics.bundle" | "app.install" | "app.uninstall" | "app.launch" | "app.stop" | "app.data.clear" | "local.data.cleanup";
    status: "succeeded" | "failed";
    started_at: string;
    completed_at: string;
    result: NavigationResult | AgentStepResult | DeviceLogCaptureResult | DevicePerformanceSnapshotResult | DiagnosticBundleResult | ApkInstallResult | AppRemovalResult | AppLifecycleResult | LocalDataCleanupResult | null;
    error: Record<string, unknown> | null;
  }>;
  evidence_summary: Record<string, unknown>;
  error: Record<string, unknown> | null;
}
