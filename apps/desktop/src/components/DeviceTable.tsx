import type { Device } from '@contracts/device'
import type { DeviceAvailability } from '@contracts/runtime-readiness'

import { StatusBadge, type BadgeTone } from './StatusBadge'

const connectionLabel: Record<Device['connection'], string> = {
  online: '在线',
  offline: '离线',
  unauthorized: '未授权',
  unknown: '未知',
}

const availabilityTone: Record<DeviceAvailability['status'], BadgeTone> = {
  ready: 'ok',
  busy: 'busy',
  offline: 'muted',
  unauthorized: 'warn',
  unknown: 'muted',
}

const availabilityLabel: Record<DeviceAvailability['status'], string> = {
  ready: '就绪',
  busy: '任务占用',
  offline: '离线',
  unauthorized: '未授权',
  unknown: '未知',
}

function shortenSession(sessionId: string | null): string {
  if (!sessionId) {
    return '—'
  }
  return sessionId.length > 20 ? `${sessionId.slice(0, 20)}…` : sessionId
}

export function DeviceTable({
  devices,
  availability,
}: {
  devices: Device[]
  availability: Map<string, DeviceAvailability>
}) {
  if (devices.length === 0) {
    return (
      <section className="panel">
        <h2>设备</h2>
        <p className="empty-state">
          未发现设备。连接 Android 设备、开启开发者选项与 USB 调试并完成授权后，设备会出现在这里。
        </p>
      </section>
    )
  }
  return (
    <section className="panel">
      <h2>设备</h2>
      <table className="device-table">
        <thead>
          <tr>
            <th>设备</th>
            <th>型号</th>
            <th>系统</th>
            <th>连接</th>
            <th>状态</th>
            <th>会话</th>
            <th>能力</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => {
            const state = availability.get(device.device_id)
            return (
              <tr key={device.device_id}>
                <td>
                  <div className="device-name">{device.name}</div>
                  <div className="device-id">{device.device_id}</div>
                </td>
                <td>{device.model}</td>
                <td>Android {device.os_version}</td>
                <td>{connectionLabel[device.connection]}</td>
                <td>
                  {state ? (
                    <StatusBadge
                      tone={availabilityTone[state.status]}
                      label={availabilityLabel[state.status]}
                    />
                  ) : (
                    '—'
                  )}
                </td>
                <td className="mono">{shortenSession(device.session_id)}</td>
                <td>
                  <span className="capability-count" title={device.capabilities.join('\n')}>
                    {device.capabilities.length} 项
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
