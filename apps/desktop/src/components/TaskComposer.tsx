import { useState } from 'react'
import { Play } from 'lucide-react'

import type { Device } from '@contracts/device'
import type { DeviceAvailability } from '@contracts/runtime-readiness'

const APP_ID_PATTERN = /^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$/

export type TaskIntent =
  | {
      kind: 'agent'
      deviceId: string
      goal: string
      maxRounds: number
      idempotencyKey: string
    }
  | {
      kind: 'stability'
      deviceId: string
      appId: string
      durationSeconds: number
      idempotencyKey: string
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
  const [mode, setMode] = useState<'agent' | 'stability'>('agent')
  const [deviceId, setDeviceId] = useState('')
  const [goal, setGoal] = useState('')
  const [appId, setAppId] = useState('')
  const [maxRounds, setMaxRounds] = useState(12)
  const selected = readyDevices.some((device) => device.device_id === deviceId)
    ? deviceId
    : (readyDevices[0]?.device_id ?? '')
  const trimmedGoal = goal.trim()
  const trimmedAppId = appId.trim()
  const appIdValid = APP_ID_PATTERN.test(trimmedAppId)
  const canSubmit =
    !busy &&
    selected !== '' &&
    (mode === 'agent' ? trimmedGoal.length > 0 : appIdValid)

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
            if (!canSubmit) {
              return
            }
            const idempotencyKey = crypto.randomUUID()
            if (mode === 'agent') {
              onSubmit({
                kind: 'agent',
                deviceId: selected,
                goal: trimmedGoal,
                maxRounds,
                idempotencyKey,
              })
              return
            }
            onSubmit({
              kind: 'stability',
              deviceId: selected,
              appId: trimmedAppId,
              durationSeconds: 120,
              idempotencyKey,
            })
          }}
        >
          <div className="composer-modes" role="tablist" aria-label="任务类型">
            <button
              type="button"
              className={mode === 'agent' ? 'primary-button' : 'plain-button'}
              aria-pressed={mode === 'agent'}
              disabled={busy}
              onClick={() => setMode('agent')}
            >
              自然语言
            </button>
            <button
              type="button"
              className={mode === 'stability' ? 'primary-button' : 'plain-button'}
              aria-pressed={mode === 'stability'}
              disabled={busy}
              onClick={() => setMode('stability')}
            >
              稳定性测试
            </button>
          </div>
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
          {mode === 'agent' ? (
            <>
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
              <label className="composer-field">
                <span className="composer-label">轮次预算</span>
                <input
                  className="composer-select"
                  type="number"
                  name="max_rounds"
                  min={1}
                  max={50}
                  value={maxRounds}
                  disabled={busy}
                  onChange={(event) => {
                    const value = Math.floor(Number(event.target.value))
                    if (Number.isFinite(value)) {
                      setMaxRounds(Math.min(50, Math.max(1, value)))
                    }
                  }}
                />
              </label>
            </>
          ) : (
            <label className="composer-field">
              <span className="composer-label">应用包名</span>
              <input
                className="composer-select"
                name="app_id"
                maxLength={128}
                placeholder="例如 com.android.settings"
                value={appId}
                disabled={busy}
                onChange={(event) => setAppId(event.target.value)}
              />
              {trimmedAppId.length > 0 && !appIdValid ? (
                <span className="composer-hint">包名需要像 com.example.app 这样的形式</span>
              ) : (
                <span className="composer-hint">约 2 分钟遍历：启动、滑动、返回，并采集性能采样</span>
              )}
            </label>
          )}
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
