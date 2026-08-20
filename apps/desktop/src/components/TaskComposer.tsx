import { useState } from 'react'
import { Play } from 'lucide-react'

import type { Device } from '@contracts/device'
import type { DeviceAvailability } from '@contracts/runtime-readiness'

export interface TaskIntent {
  deviceId: string
  goal: string
}

export function TaskComposer({
  devices,
  availability,
  busy,
  onSubmit,
}: {
  devices: Device[]
  availability: Map<string, DeviceAvailability>
  busy: boolean
  onSubmit: (intent: TaskIntent) => void
}) {
  const readyDevices = devices.filter(
    (device) => availability.get(device.device_id)?.status === 'ready',
  )
  const [deviceId, setDeviceId] = useState('')
  const [goal, setGoal] = useState('')
  const selected = readyDevices.some((device) => device.device_id === deviceId)
    ? deviceId
    : (readyDevices[0]?.device_id ?? '')
  const trimmed = goal.trim()
  const canSubmit = !busy && selected !== '' && trimmed.length > 0

  return (
    <section className="panel">
      <h2>新任务</h2>
      {readyDevices.length === 0 ? (
        <p className="empty-state">
          当前没有就绪设备。连接并授权一台 Android 设备，待状态变为“就绪”后即可提交任务。
        </p>
      ) : (
        <form
          className="composer-form"
          onSubmit={(event) => {
            event.preventDefault()
            if (canSubmit) {
              onSubmit({ deviceId: selected, goal: trimmed })
            }
          }}
        >
          <label className="composer-field">
            <span className="composer-label">目标设备</span>
            <select
              className="composer-select"
              name="device_id"
              value={selected}
              disabled={busy}
              onChange={(event) => setDeviceId(event.target.value)}
            >
              {readyDevices.map((device) => (
                <option key={device.device_id} value={device.device_id}>
                  {device.name}（Android {device.os_version}）
                </option>
              ))}
            </select>
          </label>
          <label className="composer-field">
            <span className="composer-label">任务目标</span>
            <textarea
              className="composer-textarea"
              name="goal"
              rows={3}
              maxLength={500}
              placeholder="例如：打开系统设置，进入显示和亮度页面…"
              value={goal}
              disabled={busy}
              onChange={(event) => setGoal(event.target.value)}
            />
          </label>
          <div className="composer-actions">
            <button type="submit" className="primary-button" disabled={!canSubmit}>
              <Play size={14} aria-hidden />
              提交任务
            </button>
            {busy ? <span className="composer-hint">已有任务在执行</span> : null}
          </div>
        </form>
      )}
    </section>
  )
}
