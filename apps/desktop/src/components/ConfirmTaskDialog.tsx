import { AlertTriangle } from 'lucide-react'

import type { Device } from '@contracts/device'

import type { TaskIntent } from './TaskComposer'

/**
 * Pre-submission confirmation. Submitting `confirmed: true` to the Runtime is
 * only allowed after the user explicitly approves this summary — the same
 * trust model the MCP interface documents for external agents.
 */
export function ConfirmTaskDialog({
  intent,
  device,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  intent: TaskIntent
  device: Device | undefined
  pending: boolean
  error: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="dialog-backdrop" role="presentation">
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">确认执行 Agent 任务</h2>
        <dl className="dialog-facts">
          <dt>目标</dt>
          <dd>{intent.goal}</dd>
          <dt>设备</dt>
          <dd>
            {device ? `${device.name}（Android ${device.os_version}）` : intent.deviceId}
            <span className="dialog-device-id">{intent.deviceId}</span>
          </dd>
        </dl>
        <div className="dialog-risk">
          <AlertTriangle size={15} aria-hidden />
          <p>
            Agent 将在该设备上自主执行点击、滑动和文本输入等 Medium
            风险动作。每一步决策仍受 Tool 白名单、设备能力和安全策略约束；你可以随时取消任务。
          </p>
        </div>
        {error ? <p className="error-detail">{error}</p> : null}
        <div className="dialog-actions">
          <button type="button" className="plain-button" disabled={pending} onClick={onCancel}>
            返回修改
          </button>
          <button type="button" className="primary-button" disabled={pending} onClick={onConfirm}>
            {pending ? '正在提交…' : '确认执行'}
          </button>
        </div>
      </div>
    </div>
  )
}
