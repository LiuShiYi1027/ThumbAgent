import { useQuery } from '@tanstack/react-query'
import { MonitorSmartphone } from 'lucide-react'

import {
  getTaskExecutionEvents,
  getTaskRun,
  latestScreenshotFromEvents,
  stepScreenshotArtifactId,
} from '../api/client'
import { ScreenshotImage } from './ScreenshotImage'

/**
 * The device-screen column of the workbench: while a task runs it follows the
 * event stream and shows the newest after-action screenshot; once finished it
 * pins the final round's screenshot from the persisted report.
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

  return (
    <section className="panel device-screen-panel">
      <div className="panel-title-row">
        <h2>设备画面</h2>
        {live ? <span className="screen-live-hint">随任务轮次更新</span> : null}
      </div>
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
              ? '任务产生首个动作后，这里会展示最新设备截图。'
              : '该任务没有可展示的截图证据。'}
          </span>
        </div>
      )}
    </section>
  )
}
