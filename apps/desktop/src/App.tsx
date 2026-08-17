import { useCallback, useMemo, useState } from 'react'

import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MonitorSmartphone, RefreshCw } from 'lucide-react'

import type { TaskExecution } from '@contracts/task-execution'

import { getBridgeStatus } from './api/bridge'
import { getDevices, getHealth, getReadiness, submitAgentTask } from './api/client'
import { ConfirmTaskDialog } from './components/ConfirmTaskDialog'
import { DeviceTable } from './components/DeviceTable'
import { ExecutionView } from './components/ExecutionView'
import { ReadinessPanel } from './components/ReadinessPanel'
import { StatusBadge } from './components/StatusBadge'
import { TaskComposer, type TaskIntent } from './components/TaskComposer'
import { TaskReportView } from './components/TaskReportView'
import { isTerminal } from './execution'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000,
    },
  },
})

function Workbench() {
  const client = useQueryClient()
  const statusQuery = useQuery({
    queryKey: ['bridge-status'],
    queryFn: getBridgeStatus,
    refetchInterval: (query) => (query.state.data?.phase === 'ready' ? 5000 : 1000),
  })
  const phase = statusQuery.data?.phase ?? 'starting'
  const ready = phase === 'ready'

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    enabled: ready,
    refetchInterval: 10000,
  })
  const readinessQuery = useQuery({
    queryKey: ['readiness'],
    queryFn: getReadiness,
    enabled: ready,
    refetchInterval: 3000,
  })
  const devicesQuery = useQuery({
    queryKey: ['devices'],
    queryFn: getDevices,
    enabled: ready,
    refetchInterval: 3000,
  })

  const readiness = readinessQuery.data
  const devices = useMemo(() => {
    if (devicesQuery.data) {
      return devicesQuery.data.devices
    }
    return readiness?.devices.map((entry) => entry.device) ?? []
  }, [devicesQuery.data, readiness])
  const availability = useMemo(
    () => new Map((readiness?.devices ?? []).map((entry) => [entry.device.device_id, entry])),
    [readiness],
  )

  // One active task at a time: the composer is hidden while an execution is
  // live, and the finished execution keeps its report on screen until the
  // user starts a new task.
  const [pendingIntent, setPendingIntent] = useState<TaskIntent | null>(null)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [finishedExecution, setFinishedExecution] = useState<TaskExecution | null>(null)

  const submitMutation = useMutation({
    mutationFn: (intent: TaskIntent) => submitAgentTask(intent.deviceId, intent.goal),
    onSuccess: (execution) => {
      setPendingIntent(null)
      setFinishedExecution(null)
      setActiveTaskId(execution.task_id)
    },
  })

  const handleTerminal = useCallback((execution: TaskExecution) => {
    setActiveTaskId(null)
    setFinishedExecution(execution)
  }, [])

  const resetForNewTask = useCallback(() => {
    setFinishedExecution(null)
    setActiveTaskId(null)
  }, [])

  const refreshing =
    readinessQuery.isFetching || devicesQuery.isFetching || statusQuery.isFetching
  const taskBusy = activeTaskId !== null

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <MonitorSmartphone className="app-logo" aria-hidden />
          <div>
            <h1>Mobile Agent</h1>
            <span className="app-subtitle">
              {healthQuery.data
                ? `Runtime ${healthQuery.data.runtime_version} · API ${healthQuery.data.api_version}`
                : '本地设备工作台'}
            </span>
          </div>
        </div>
        <div className="header-actions">
          {phase === 'ready' ? (
            <StatusBadge tone="ok" label="Runtime 就绪" />
          ) : phase === 'failed' ? (
            <StatusBadge tone="error" label="Runtime 异常" />
          ) : (
            <StatusBadge tone="loading" label="Runtime 启动中" />
          )}
          <button
            type="button"
            className="icon-button"
            title="刷新设备与诊断状态"
            disabled={!ready}
            onClick={() => void client.invalidateQueries()}
          >
            <RefreshCw className={refreshing ? 'spin' : ''} size={16} aria-hidden />
          </button>
        </div>
      </header>

      <main className="app-main">
        {phase === 'failed' ? (
          <section className="panel panel-error">
            <h2>本地 Runtime 启动失败</h2>
            <p className="error-detail">{statusQuery.data?.detail}</p>
          </section>
        ) : null}

        {ready && readinessQuery.isError ? (
          <section className="panel panel-error">
            <h2>无法获取就绪诊断</h2>
            <p className="error-detail">{String(readinessQuery.error)}</p>
          </section>
        ) : null}

        {readiness ? <ReadinessPanel readiness={readiness} /> : null}
        {ready ? <DeviceTable devices={devices} availability={availability} /> : null}

        {ready && !taskBusy && !finishedExecution ? (
          <TaskComposer
            devices={devices}
            availability={availability}
            busy={submitMutation.isPending}
            onSubmit={setPendingIntent}
          />
        ) : null}

        {activeTaskId ? (
          <ExecutionView taskId={activeTaskId} onTerminal={handleTerminal} />
        ) : null}

        {finishedExecution ? (
          <>
            <section className="panel">
              <div className="panel-title-row">
                <h2>任务已结束</h2>
                <button type="button" className="plain-button" onClick={resetForNewTask}>
                  开始新任务
                </button>
              </div>
              <p className="empty-state">
                {finishedExecution.goal}（{isTerminal(finishedExecution) ? finishedExecution.status : ''}）
              </p>
            </section>
            {finishedExecution.result_available ? (
              <TaskReportView taskId={finishedExecution.task_id} />
            ) : null}
          </>
        ) : null}
      </main>

      {pendingIntent ? (
        <ConfirmTaskDialog
          intent={pendingIntent}
          device={devices.find((device) => device.device_id === pendingIntent.deviceId)}
          pending={submitMutation.isPending}
          error={submitMutation.isError ? String(submitMutation.error) : null}
          onConfirm={() => submitMutation.mutate(pendingIntent)}
          onCancel={() => {
            submitMutation.reset()
            setPendingIntent(null)
          }}
        />
      ) : null}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Workbench />
    </QueryClientProvider>
  )
}
