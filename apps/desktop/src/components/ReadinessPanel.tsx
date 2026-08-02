import { Cable } from 'lucide-react'

import type { Issue, RuntimeReadiness } from '@contracts/runtime-readiness'

import { StatusBadge, type BadgeTone } from './StatusBadge'

const statusTone: Record<RuntimeReadiness['status'], BadgeTone> = {
  ready: 'ok',
  attention: 'warn',
  blocked: 'error',
}

const statusLabel: Record<RuntimeReadiness['status'], string> = {
  ready: '就绪',
  attention: '需关注',
  blocked: '受阻',
}

function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) {
    return null
  }
  return (
    <ul className="issue-list">
      {issues.map((issue, index) => (
        <li key={`${issue.code}-${index}`} className="issue-item">
          <code className="issue-code">{issue.code}</code>
          <div>
            <div className="issue-message">{issue.message}</div>
            {issue.suggested_action ? (
              <div className="issue-action">建议：{issue.suggested_action}</div>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function ReadinessPanel({ readiness }: { readiness: RuntimeReadiness }) {
  const { gateway, summary } = readiness
  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>运行环境</h2>
        <StatusBadge tone={statusTone[readiness.status]} label={statusLabel[readiness.status]} />
      </div>

      <div className="gateway-row">
        <Cable className="gateway-icon" aria-hidden />
        <div>
          <div className="gateway-name">
            {gateway.platform} · {gateway.transport}
          </div>
          <div className="gateway-sub">
            {gateway.status === 'available' ? '驱动可用' : '驱动不可用'}
          </div>
        </div>
        <div className="summary-counts">
          <span>设备 {summary.total}</span>
          <span className="count-ok">就绪 {summary.ready}</span>
          <span className="count-busy">占用 {summary.busy}</span>
          <span className={summary.attention > 0 ? 'count-warn' : ''}>需关注 {summary.attention}</span>
        </div>
      </div>

      {gateway.issue ? <IssueList issues={[gateway.issue]} /> : null}
      <IssueList issues={readiness.issues} />

      <div className="panel-foot">诊断生成于 {new Date(readiness.generated_at).toLocaleString()}</div>
    </section>
  )
}
