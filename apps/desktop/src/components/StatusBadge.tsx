import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react'

export type BadgeTone = 'ok' | 'warn' | 'error' | 'busy' | 'muted' | 'loading'

const toneLabels: Record<BadgeTone, string> = {
  ok: '正常',
  warn: '需关注',
  error: '异常',
  busy: '占用',
  muted: '未知',
  loading: '检查中',
}

export function StatusBadge({ tone, label }: { tone: BadgeTone; label?: string }) {
  return (
    <span className={`badge badge-${tone}`}>
      {tone === 'loading' ? (
        <Loader2 className="badge-icon spin" aria-hidden />
      ) : tone === 'ok' ? (
        <CheckCircle2 className="badge-icon" aria-hidden />
      ) : tone === 'warn' || tone === 'busy' ? (
        <AlertTriangle className="badge-icon" aria-hidden />
      ) : tone === 'error' ? (
        <XCircle className="badge-icon" aria-hidden />
      ) : null}
      {label ?? toneLabels[tone]}
    </span>
  )
}
