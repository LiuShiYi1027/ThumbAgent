import { useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { AgentStepResult } from '@contracts/agent-step-result'
import type { TaskEvent } from '@contracts/task-event'
import type { TaskRun } from '@contracts/task-run'

import { getTaskExecutionEvents, getTaskRun, stepScreenshotArtifactId } from '../api/client'
import { ScreenshotImage } from './ScreenshotImage'
import { StatusBadge, type BadgeTone } from './StatusBadge'

const runStatusLabel: Record<TaskRun['status'], string> = {
  succeeded: '已成功',
  failed: '已失败',
  cancelled: '已取消',
  timed_out: '已超时',
}

const runStatusTone: Record<TaskRun['status'], BadgeTone> = {
  succeeded: 'ok',
  failed: 'error',
  cancelled: 'muted',
  timed_out: 'warn',
}

const completionSourceLabel: Record<
  NonNullable<TaskRun['completion_source']>,
  string
> = {
  planner_finish: '模型判定完成',
  runtime_acceptance: 'Runtime 验收完成',
  skill_result: 'Skill 结果完成',
}

const decisionTypeLabel: Record<string, string> = {
  run_tool: '执行工具',
  run_skill: '执行 Skill',
  finish: '请求完成',
}

function errorSummary(error: Record<string, unknown> | null): string | null {
  if (!error) {
    return null
  }
  const code = typeof error.code === 'string' ? error.code : ''
  const message = typeof error.message === 'string' ? error.message : ''
  if (!code && !message) {
    return null
  }
  return code ? `${code}：${message}` : message
}

function asAgentStepResult(result: unknown): AgentStepResult | null {
  if (result && typeof result === 'object' && 'decision' in result) {
    return result as AgentStepResult
  }
  return null
}

function formatArguments(args: Record<string, unknown>): string {
  const text = JSON.stringify(args, null, 0)
  return text.length > 160 ? `${text.slice(0, 160)}…` : text
}

interface TakeoverInterval {
  start: string
  end: string | null
  reason: string | null
}

/** 从事件流提取暂停-恢复区间；报告据此区分 Agent 动作与人工接管窗口。 */
function collectTakeoverIntervals(events: TaskEvent[]): TakeoverInterval[] {
  const intervals: TakeoverInterval[] = []
  for (const event of events) {
    if (event.event_type === 'task.paused') {
      intervals.push({ start: event.occurred_at, end: null, reason: null })
    } else if (event.event_type === 'task.resumed') {
      const open = intervals.findLast((interval) => interval.end === null)
      if (open) {
        open.end = event.occurred_at
        open.reason =
          typeof event.payload.resume_reason === 'string' ? event.payload.resume_reason : null
      }
    }
  }
  return intervals
}

function takeoverReasonLabel(reason: string | null): string {
  switch (reason) {
    case 'user':
      return '用户恢复'
    case 'cancel':
      return '因取消请求结束'
    case 'deadline':
      return '因任务预算到期结束'
    default:
      return '原因未记录'
  }
}

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString()
}

export function TaskReportView({ taskId }: { taskId: string }) {
  const [expandedSteps, setExpandedSteps] = useState<ReadonlySet<string>>(new Set())
  const reportQuery = useQuery({
    queryKey: ['task-run', taskId],
    queryFn: () => getTaskRun(taskId),
    refetchInterval: false,
    staleTime: Infinity,
  })
  const eventsQuery = useQuery({
    queryKey: ['task-execution-events', taskId],
    queryFn: () => getTaskExecutionEvents(taskId),
    refetchInterval: false,
    staleTime: Infinity,
  })

  const toggleStep = (stepId: string) => {
    setExpandedSteps((current) => {
      const next = new Set(current)
      if (next.has(stepId)) {
        next.delete(stepId)
      } else {
        next.add(stepId)
      }
      return next
    })
  }

  if (reportQuery.isPending) {
    return (
      <section className="panel">
        <h2>任务报告</h2>
        <p className="empty-state">正在加载任务报告…</p>
      </section>
    )
  }
  if (reportQuery.isError || !reportQuery.data) {
    return (
      <section className="panel panel-error">
        <h2>任务报告</h2>
        <p className="error-detail">{String(reportQuery.error ?? '报告不可用')}</p>
      </section>
    )
  }

  const report = reportQuery.data
  const taskError = errorSummary(report.error)
  const takeoverIntervals = collectTakeoverIntervals(eventsQuery.data ?? [])

  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>任务报告</h2>
        <StatusBadge
          tone={runStatusTone[report.status]}
          label={runStatusLabel[report.status]}
        />
      </div>
      <p className="execution-goal">{report.goal}</p>
      <div className="execution-meta">
        <span className="mono">{report.task_id}</span>
        {report.completion_source ? (
          <span>{completionSourceLabel[report.completion_source]}</span>
        ) : null}
        <span>
          {new Date(report.started_at).toLocaleTimeString()} —{' '}
          {new Date(report.completed_at).toLocaleTimeString()}
        </span>
      </div>
      {taskError ? <p className="error-detail">{taskError}</p> : null}
      {takeoverIntervals.length > 0 ? (
        <div className="execution-meta">
          {takeoverIntervals.map((interval, index) => (
            <span key={`${interval.start}-${index}`} className="takeover-hint">
              人工接管 {formatClock(interval.start)} —{' '}
              {interval.end ? formatClock(interval.end) : '未闭合'}（
              {takeoverReasonLabel(interval.reason)}）
            </span>
          ))}
        </div>
      ) : null}
      <ol className="step-list">
        {report.steps.map((step) => {
          const agentStep = step.kind === 'agent_round' ? asAgentStepResult(step.result) : null
          const stepError = errorSummary(step.error)
          const screenshotId = stepScreenshotArtifactId(step)
          const expanded = expandedSteps.has(step.step_id)
          return (
            <li key={step.step_id} className={step.status === 'failed' ? 'event-failed' : ''}>
              <div className="step-head">
                <span className="step-title">
                  第 {step.sequence} 轮
                  {agentStep
                    ? ` · ${decisionTypeLabel[agentStep.decision.decision_type] ?? agentStep.decision.decision_type}`
                    : ` · ${step.name}`}
                </span>
                <span className="step-head-actions">
                  {screenshotId ? (
                    <button
                      type="button"
                      className="plain-button step-screenshot-toggle"
                      onClick={() => toggleStep(step.step_id)}
                    >
                      {expanded ? '收起截图' : '查看截图'}
                    </button>
                  ) : null}
                  <StatusBadge
                    tone={step.status === 'succeeded' ? 'ok' : 'error'}
                    label={step.status === 'succeeded' ? '成功' : '失败'}
                  />
                </span>
              </div>
              {agentStep ? (
                <div className="step-detail">
                  <div>
                    动作：
                    <code>
                      {agentStep.decision.decision_type === 'run_skill'
                        ? agentStep.decision.skill_id
                        : agentStep.decision.tool_id || '—'}
                    </code>
                    <span className="mono">{formatArguments(agentStep.decision.arguments)}</span>
                  </div>
                  <div>依据：{agentStep.decision.reason}</div>
                  {agentStep.action_feedback ? (
                    <div>
                      页面进展：
                      {{ changed: '有变化', unchanged: '无变化', unknown: '未知' }[
                        agentStep.action_feedback.effect
                      ] ?? agentStep.action_feedback.effect}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {stepError ? <p className="error-detail">{stepError}</p> : null}
              {expanded && screenshotId ? (
                <ScreenshotImage
                  artifactId={screenshotId}
                  alt={`第 ${step.sequence} 轮动作后的设备截图`}
                />
              ) : null}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
