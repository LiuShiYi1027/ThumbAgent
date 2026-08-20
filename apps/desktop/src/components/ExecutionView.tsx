import { useEffect, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Ban, Pause, Play } from 'lucide-react'

import type { TaskEvent } from '@contracts/task-event'
import type { TaskExecution } from '@contracts/task-execution'

import {
  cancelTaskExecution,
  getTaskExecution,
  getTaskExecutionEvents,
  pauseTaskExecution,
  resumeTaskExecution,
} from '../api/client'
import { isTerminal } from '../execution'
import { StatusBadge, type BadgeTone } from './StatusBadge'

const statusLabel: Record<TaskExecution['status'], string> = {
  queued: '排队中',
  running: '执行中',
  paused: '已暂停（人工接管）',
  cancelling: '取消中',
  succeeded: '已成功',
  failed: '已失败',
  cancelled: '已取消',
  timed_out: '已超时',
}

const statusTone: Record<TaskExecution['status'], BadgeTone> = {
  queued: 'muted',
  running: 'busy',
  paused: 'warn',
  cancelling: 'warn',
  succeeded: 'ok',
  failed: 'error',
  cancelled: 'muted',
  timed_out: 'warn',
}

function eventLabel(event: TaskEvent, roundIndex: number): string {
  switch (event.event_type) {
    case 'task.queued':
      return '任务已排队'
    case 'task.started':
      return '任务开始执行'
    case 'task.step_completed': {
      const status = typeof event.payload.status === 'string' ? event.payload.status : ''
      const errorCode =
        typeof event.payload.error_code === 'string' && event.payload.error_code !== ''
          ? `（${event.payload.error_code}）`
          : ''
      return status === 'failed'
        ? `第 ${roundIndex} 轮失败${errorCode}`
        : `第 ${roundIndex} 轮完成`
    }
    case 'task.cancel_requested':
      return '已请求取消，将在安全边界停止'
    case 'task.pause_requested':
      return '已请求暂停，将在安全边界进入人工接管'
    case 'task.paused':
      return '已暂停：人工接管中，可直接操作设备'
    case 'task.resumed': {
      const reason = typeof event.payload.resume_reason === 'string' ? event.payload.resume_reason : ''
      if (reason === 'cancel') {
        return '暂停结束：任务按取消请求收尾'
      }
      if (reason === 'deadline') {
        return '暂停结束：任务预算已到期'
      }
      return '已恢复：Agent 重新观察设备画面后继续'
    }
    case 'task.completed': {
      const status = typeof event.payload.status === 'string' ? event.payload.status : ''
      const errorCode =
        typeof event.payload.error_code === 'string' && event.payload.error_code !== ''
          ? `（${event.payload.error_code}）`
          : ''
      return `任务结束：${statusLabel[status as TaskExecution['status']] ?? status}${errorCode}`
    }
    default:
      return event.event_type
  }
}

export function ExecutionView({
  taskId,
  onTerminal,
}: {
  taskId: string
  onTerminal: (execution: TaskExecution) => void
}) {
  const executionQuery = useQuery({
    queryKey: ['task-execution', taskId],
    queryFn: () => getTaskExecution(taskId),
    refetchInterval: (query) =>
      query.state.data && isTerminal(query.state.data) ? false : 1200,
  })
  const eventsQuery = useQuery({
    queryKey: ['task-execution-events', taskId],
    queryFn: () => getTaskExecutionEvents(taskId),
    refetchInterval: () => (executionQuery.data && isTerminal(executionQuery.data) ? false : 1200),
  })
  const cancelMutation = useMutation({
    mutationFn: () => cancelTaskExecution(taskId),
  })
  const pauseMutation = useMutation({
    mutationFn: () => pauseTaskExecution(taskId),
  })
  const resumeMutation = useMutation({
    mutationFn: () => resumeTaskExecution(taskId),
  })

  const execution = executionQuery.data
  const terminalNotified = useRef(false)
  useEffect(() => {
    if (execution && isTerminal(execution) && !terminalNotified.current) {
      terminalNotified.current = true
      onTerminal(execution)
    }
  }, [execution, onTerminal])

  if (!execution) {
    return (
      <section className="panel">
        <h2>执行状态</h2>
        <p className="empty-state">正在加载任务状态…</p>
      </section>
    )
  }

  const events = eventsQuery.data ?? []
  let roundCounter = 0

  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>执行状态</h2>
        <StatusBadge tone={statusTone[execution.status]} label={statusLabel[execution.status]} />
      </div>
      <p className="execution-goal">{execution.goal}</p>
      <div className="execution-meta">
        <span className="mono">{execution.task_id}</span>
        <span>Deadline {execution.deadline_seconds} 秒</span>
        {execution.cancel_requested ? <span>取消请求已记录</span> : null}
      </div>
      <ol className="event-timeline">
        {events.map((event) => {
          if (event.event_type === 'task.step_completed') {
            roundCounter += 1
          }
          const failed =
            event.event_type === 'task.step_completed' && event.payload.status === 'failed'
          return (
            <li key={event.event_id} className={failed ? 'event-failed' : ''}>
              <span className="event-label">{eventLabel(event, roundCounter)}</span>
              <span className="event-time">
                {new Date(event.occurred_at).toLocaleTimeString()}
              </span>
            </li>
          )
        })}
      </ol>
      {execution.error ? (
        <p className="error-detail">{JSON.stringify(execution.error)}</p>
      ) : null}
      {execution.status === 'paused' ? (
        <p className="takeover-banner" role="status">
          <Pause size={14} aria-hidden />
          任务已暂停：你现在可以直接操作设备；恢复后 Agent 会重新观察画面并继续规划。
        </p>
      ) : null}
      {cancelMutation.isError ? (
        <p className="error-detail">{String(cancelMutation.error)}</p>
      ) : null}
      {pauseMutation.isError ? (
        <p className="error-detail">{String(pauseMutation.error)}</p>
      ) : null}
      {resumeMutation.isError ? (
        <p className="error-detail">{String(resumeMutation.error)}</p>
      ) : null}
      {!isTerminal(execution) ? (
        <div className="composer-actions">
          {execution.status === 'paused' ? (
            <button
              type="button"
              className="plain-button"
              disabled={resumeMutation.isPending}
              onClick={() => resumeMutation.mutate()}
            >
              <Play size={14} aria-hidden />
              恢复执行
            </button>
          ) : (
            <button
              type="button"
              className="plain-button"
              disabled={
                pauseMutation.isPending ||
                execution.pause_requested ||
                execution.cancel_requested ||
                execution.status !== 'running'
              }
              onClick={() => pauseMutation.mutate()}
            >
              <Pause size={14} aria-hidden />
              {execution.pause_requested ? '已请求暂停' : '暂停（人工接管）'}
            </button>
          )}
          <button
            type="button"
            className="plain-button"
            disabled={cancelMutation.isPending || execution.cancel_requested}
            onClick={() => cancelMutation.mutate()}
          >
            <Ban size={14} aria-hidden />
            {execution.cancel_requested ? '已请求取消' : '取消任务'}
          </button>
        </div>
      ) : null}
    </section>
  )
}
