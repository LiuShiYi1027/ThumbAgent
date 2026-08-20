import { useQuery } from '@tanstack/react-query'
import { Hand, MonitorSmartphone } from 'lucide-react'

import {
  getTaskExecution,
  getTaskExecutionEvents,
  getTaskRun,
  latestScreenshotFromEvents,
  stepScreenshotArtifactId,
} from '../api/client'
import { ScreenshotImage } from './ScreenshotImage'

/**
 * The device-screen column of the workbench: while a task runs it follows the
 * event stream and shows the newest after-action screenshot; once finished it
 * pins the final round's screenshot from the persisted report. 暂停（人工接管）
 * 期间保留最后一帧并提示接管状态——Agent 不再产生新截图。
 */
export function DeviceScreenPanel({
  taskId,
  live,
}: {
  taskId: string
  live: boolean
}) {
  const eventsQuery = useQuery({
    queryKey: ['task-execution-events', taskId],
    queryFn: () => getTaskExecutionEvents(taskId),
    refetchInterval: () => (live ? 1200 : false),
  })
  const executionQuery = useQuery({
    queryKey: ['task-execution', taskId],
    queryFn: () => getTaskExecution(taskId),
    refetchInterval: () => (live ? 1200 : false),
  })
  const reportQuery = useQuery({
    queryKey: ['task-run', taskId],
    queryFn: () => getTaskRun(taskId),
    enabled: !live,
    refetchInterval: false,
    staleTime: Infinity,
  })

  let artifactId: string | null = null
  if (live) {
    artifactId = latestScreenshotFromEvents(eventsQuery.data ?? [])
  } else if (reportQuery.data) {
    for (let index = reportQuery.data.steps.length - 1; index >= 0; index -= 1) {
      artifactId = stepScreenshotArtifactId(reportQuery.data.steps[index])
      if (artifactId) {
        break
      }
    }
  }
  const paused = live && executionQuery.data?.status === 'paused'

  return (
    <section className="panel device-screen-panel">
      <div className="panel-title-row">
        <h2>设备画面</h2>
        {live && !paused ? <span className="screen-live-hint">随任务轮次更新</span> : null}
        {paused ? <span className="takeover-hint">人工接管中</span> : null}
      </div>
      {paused ? (
        <p className="takeover-banner" role="status">
          <Hand size={14} aria-hidden />
          Agent 已暂停，画面停留在最后一帧；恢复后随下一轮动作更新。
        </p>
      ) : null}
      {artifactId ? (
        <ScreenshotImage
          artifactId={artifactId}
          alt={live ? '任务执行中的最新设备截图' : '任务最后一轮动作后的设备截图'}
        />
      ) : (
        <div className="screenshot-placeholder">
          <MonitorSmartphone size={18} aria-hidden />
          <span>
            {live
              ? paused
                ? '暂停发生在首个动作之前，恢复后这里会展示最新设备截图。'
                : '任务产生首个动作后，这里会展示最新设备截图。'
              : '该任务没有可展示的截图证据。'}
          </span>
        </div>
      )}
    </section>
  )
}
