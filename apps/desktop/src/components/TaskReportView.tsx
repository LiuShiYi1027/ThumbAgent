import { useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { AgentStepResult } from '@contracts/agent-step-result'
import type { TaskEvent } from '@contracts/task-event'
import type { TaskRun } from '@contracts/task-run'

import {
  asCrashCheck,
  asSamplingSeries,
  getTaskExecutionEvents,
  getTaskRun,
  stepScreenshotArtifactId,
  type SamplingSeriesPoint,
} from '../api/client'
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
  runtime_shortcut: '程序化捷径完成',
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

/* ITER-0065: 稳定性报告——性能采样趋势（纯 SVG，mono 主题）。
   数据形状由 client.ts 的 asSamplingSeries/asCrashCheck 在边界窄化。 */

interface SamplingMetric {
  key: string
  label: string
  className: string
  pick: (point: SamplingSeriesPoint) => number
  format: (value: number) => string
}

const samplingMetrics: SamplingMetric[] = [
  {
    key: 'cpu',
    label: 'CPU',
    className: 'sampling-line-cpu',
    pick: (point) => point.cpu.total_usage_percent,
    format: (value) => `${value.toFixed(1)}%`,
  },
  {
    key: 'memory',
    label: '内存',
    className: 'sampling-line-memory',
    pick: (point) => point.memory.used_percent,
    format: (value) => `${value.toFixed(1)}%`,
  },
  {
    key: 'battery',
    label: '电池',
    className: 'sampling-line-battery',
    pick: (point) => point.battery.level_percent,
    format: (value) => `${value.toFixed(0)}%`,
  },
]

/** 紧凑 SVG 趋势图：CPU/内存/电池均为 0–100 百分比，共用一根轴。 */
function SamplingSeriesChart({ points }: { points: SamplingSeriesPoint[] }) {
  const width = 560
  const height = 120
  const padX = 10
  const padY = 12
  const xAt = (index: number): number =>
    points.length === 1
      ? width / 2
      : padX + (index * (width - padX * 2)) / (points.length - 1)
  const yAt = (value: number): number =>
    padY + (1 - Math.min(100, Math.max(0, value)) / 100) * (height - padY * 2)
  const latest = points[points.length - 1]
  return (
    <div className="sampling-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`性能采样趋势，共 ${points.length} 次采样`}
        preserveAspectRatio="none"
      >
        {[0, 25, 50, 75, 100].map((tick) => (
          <line
            key={tick}
            className="sampling-grid"
            x1={padX}
            x2={width - padX}
            y1={yAt(tick)}
            y2={yAt(tick)}
          />
        ))}
        {samplingMetrics.map((metric) => (
          <polyline
            key={metric.key}
            className={`sampling-line ${metric.className}`}
            points={points.map((point, index) => `${xAt(index)},${yAt(metric.pick(point))}`).join(' ')}
          />
        ))}
        {points.map((point, index) => (
          <rect
            key={point.step_id}
            className="sampling-dot"
            x={xAt(index) - 2.5}
            y={yAt(point.cpu.total_usage_percent) - 2.5}
            width={5}
            height={5}
          />
        ))}
      </svg>
      <div className="sampling-axis">
        <span>{formatClock(points[0].captured_at)}</span>
        <span>{formatClock(points[points.length - 1].captured_at)}</span>
      </div>
      <div className="sampling-legend">
        {samplingMetrics.map((metric) => (
          <span key={metric.key} className="sampling-legend-item">
            <span className={`sampling-swatch ${metric.className}`} aria-hidden />
            {metric.label} {metric.format(metric.pick(latest))}
          </span>
        ))}
      </div>
    </div>
  )
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
  // ITER-0061: surface the agent's final answer when the run produced one.
  const answer = report.result?.answer?.replace(/\s+/g, ' ').trim()
  // ITER-0065: stability evidence; absent fields degrade to no block at all.
  const samplingSeries = asSamplingSeries(report.evidence_summary.sampling_series)
  const crashCheck = asCrashCheck(report.evidence_summary.crash_check)

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
      {answer ? (
        <div className="report-answer">
          <span className="report-answer-label">结论</span>
          <p className="report-answer-text">{answer}</p>
        </div>
      ) : null}
      {crashCheck ? (
        <div className="report-crash-check">
          {crashCheck.signatures.length === 0 ? (
            <StatusBadge
              tone="ok"
              label={`未检测到崩溃/ANR 签名（检查 ${crashCheck.checked_lines} 行）`}
            />
          ) : (
            <>
              <StatusBadge
                tone="error"
                label={`检测到 ${crashCheck.signatures.length} 个崩溃/ANR 签名`}
              />
              <ul className="crash-signature-list">
                {crashCheck.signatures.map((signature, index) => (
                  <li key={`${signature.kind}-${index}`}>
                    <span className="crash-signature-kind">
                      {signature.kind === 'crash' ? '崩溃' : 'ANR'}
                    </span>
                    <span className="mono">{signature.summary}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ) : null}
      {samplingSeries ? (
        <div className="report-sampling">
          <span className="report-sampling-label">
            性能采样序列（{samplingSeries.length} 次）
          </span>
          <SamplingSeriesChart points={samplingSeries} />
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
                  {agentStep.decision.scratchpad ? (
                    <div>
                      工作记忆：
                      <span className="mono">{agentStep.decision.scratchpad}</span>
                    </div>
                  ) : null}
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
