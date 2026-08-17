import type { TaskExecution } from '@contracts/task-execution'

const TERMINAL_STATUSES = ['succeeded', 'failed', 'cancelled', 'timed_out']

/** Whether the execution reached a terminal state and stopped changing. */
export function isTerminal(execution: TaskExecution): boolean {
  return TERMINAL_STATUSES.includes(execution.status)
}
