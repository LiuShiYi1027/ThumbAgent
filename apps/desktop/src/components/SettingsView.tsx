import { useEffect, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, FolderOpen, KeyRound } from 'lucide-react'

import {
  clearModelSecret,
  getDataDirPath,
  isModelSecretStored,
  restartRuntime,
  revealDataDir,
  storeModelSecret,
} from '../api/bridge'
import {
  getModelProviderConfig,
  saveModelProviderConfig,
  type ModelProviderConfig,
} from '../api/client'
import { StatusBadge } from './StatusBadge'

interface SettingsForm {
  enabled: boolean
  baseUrl: string
  model: string
  timeoutSeconds: string
  secret: string
}

function formFromConfig(config: ModelProviderConfig): SettingsForm {
  return {
    enabled: config.enabled,
    baseUrl: config.base_url,
    model: config.model,
    timeoutSeconds: String(config.timeout_seconds),
    secret: '',
  }
}

/**
 * 设置页：模型 Provider 开箱配置。密钥只进系统钥匙串，配置文件只保存
 * env: 引用；保存后必须重启 Runtime 才生效（sidecar 重启换新令牌，
 * 进行中的任务会随旧进程终止，因此需要先确认）。
 */
export function SettingsView({ taskBusy }: { taskBusy: boolean }) {
  const client = useQueryClient()
  const configQuery = useQuery({
    queryKey: ['model-provider-config'],
    queryFn: getModelProviderConfig,
  })
  const secretQuery = useQuery({
    queryKey: ['model-secret-stored'],
    queryFn: isModelSecretStored,
  })
  const dataDirQuery = useQuery({
    queryKey: ['data-dir'],
    queryFn: getDataDirPath,
  })

  const [form, setForm] = useState<SettingsForm | null>(null)
  const [confirmingRestart, setConfirmingRestart] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    if (configQuery.data && form === null) {
      setForm(formFromConfig(configQuery.data))
    }
  }, [configQuery.data, form])

  const saveMutation = useMutation({
    mutationFn: async (values: SettingsForm) => {
      const timeout = Number(values.timeoutSeconds)
      if (!Number.isFinite(timeout) || timeout < 1 || timeout > 120) {
        throw new Error('超时时间必须是 1 到 120 秒之间的数字')
      }
      if (values.enabled && (!values.baseUrl.trim() || !values.model.trim())) {
        throw new Error('启用模型时必须填写 Base URL 和模型名称')
      }
      if (values.enabled && !values.secret.trim() && !secretQuery.data) {
        throw new Error('启用模型前请先保存 API 密钥')
      }
      if (values.secret.trim()) {
        await storeModelSecret(values.secret.trim())
      }
      return saveModelProviderConfig({
        enabled: values.enabled,
        provider: 'openai_compatible',
        base_url: values.baseUrl.trim(),
        model: values.model.trim(),
        timeout_seconds: timeout,
      })
    },
    onSuccess: () => {
      setForm((current) => (current ? { ...current, secret: '' } : current))
      void client.invalidateQueries({ queryKey: ['model-secret-stored'] })
      void client.invalidateQueries({ queryKey: ['model-provider-config'] })
      if (taskBusy) {
        setConfirmingRestart(true)
      } else {
        restartMutation.mutate()
      }
    },
  })

  const restartMutation = useMutation({
    mutationFn: restartRuntime,
    onSuccess: () => {
      setConfirmingRestart(false)
      setFeedback('配置已保存，Runtime 正在重启…')
      void client.invalidateQueries()
    },
    onError: () => {
      setConfirmingRestart(false)
    },
  })

  const clearSecretMutation = useMutation({
    mutationFn: clearModelSecret,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['model-secret-stored'] })
    },
  })

  const revealMutation = useMutation({ mutationFn: revealDataDir })

  if (configQuery.isLoading || form === null) {
    return (
      <section className="panel">
        <h2>设置</h2>
        <p className="empty-state">正在读取模型配置…</p>
      </section>
    )
  }
  if (configQuery.isError) {
    return (
      <section className="panel panel-error">
        <h2>无法读取模型配置</h2>
        <p className="error-detail">{String(configQuery.error)}</p>
      </section>
    )
  }

  const config = configQuery.data
  if (!config) {
    return (
      <section className="panel panel-error">
        <h2>无法读取模型配置</h2>
        <p className="error-detail">配置响应为空</p>
      </section>
    )
  }
  const busy =
    saveMutation.isPending ||
    restartMutation.isPending ||
    clearSecretMutation.isPending
  const errorMessage =
    (saveMutation.isError && String(saveMutation.error)) ||
    (restartMutation.isError && String(restartMutation.error)) ||
    (clearSecretMutation.isError && String(clearSecretMutation.error)) ||
    null

  return (
    <>
      <section className="panel">
        <div className="panel-title-row">
          <h2>模型 Provider</h2>
          {config.enabled ? (
            <StatusBadge tone="ok" label="已启用" />
          ) : (
            <StatusBadge tone="muted" label="未启用（使用内置规则规划器）" />
          )}
        </div>
        <p className="composer-hint">
          配置兼容 OpenAI 的模型服务后，Agent 任务将由模型决策。API
          密钥只保存在系统钥匙串中，配置生效需要重启本地 Runtime。
        </p>
        {config.env_override ? (
          <div className="dialog-risk settings-warning">
            <AlertTriangle size={15} aria-hidden />
            <p>
              检测到 MOBILE_AGENT_MODEL_* 环境变量，其值优先于此处保存的配置；此页修改可能不会生效。
            </p>
          </div>
        ) : null}

        <form
          className="composer-form"
          onSubmit={(event) => {
            event.preventDefault()
            setFeedback(null)
            saveMutation.mutate(form)
          }}
        >
          <label className="composer-field settings-toggle">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) =>
                setForm({ ...form, enabled: event.target.checked })
              }
            />
            <span className="composer-label">启用模型规划器</span>
          </label>

          <label className="composer-field">
            <span className="composer-label">Base URL</span>
            <input
              className="composer-select"
              type="text"
              placeholder="https://api.siliconflow.cn/v1"
              value={form.baseUrl}
              onChange={(event) => setForm({ ...form, baseUrl: event.target.value })}
            />
          </label>

          <label className="composer-field">
            <span className="composer-label">模型名称</span>
            <input
              className="composer-select"
              type="text"
              placeholder="例如 moonshotai/Kimi-K2-Instruct"
              value={form.model}
              onChange={(event) => setForm({ ...form, model: event.target.value })}
            />
          </label>

          <label className="composer-field">
            <span className="composer-label">超时时间（秒，1–120）</span>
            <input
              className="composer-select"
              type="number"
              min={1}
              max={120}
              value={form.timeoutSeconds}
              onChange={(event) =>
                setForm({ ...form, timeoutSeconds: event.target.value })
              }
            />
          </label>

          <label className="composer-field">
            <span className="composer-label">
              API 密钥{' '}
              {secretQuery.data ? (
                <StatusBadge tone="ok" label="已保存在钥匙串" />
              ) : (
                <StatusBadge tone="warn" label="未保存" />
              )}
            </span>
            <input
              className="composer-select"
              type="password"
              autoComplete="off"
              placeholder={secretQuery.data ? '输入新密钥以替换' : '粘贴 API 密钥'}
              value={form.secret}
              onChange={(event) => setForm({ ...form, secret: event.target.value })}
            />
          </label>

          {errorMessage ? <p className="error-detail">{errorMessage}</p> : null}
          {feedback ? <p className="composer-hint">{feedback}</p> : null}

          <div className="composer-actions">
            <button type="submit" className="primary-button" disabled={busy}>
              {saveMutation.isPending
                ? '正在保存…'
                : restartMutation.isPending
                  ? '正在重启 Runtime…'
                  : '保存并重启'}
            </button>
            <button
              type="button"
              className="plain-button"
              disabled={busy || !secretQuery.data}
              onClick={() => clearSecretMutation.mutate()}
            >
              <KeyRound size={14} aria-hidden /> 清除已存密钥
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>本地数据</h2>
        <p className="empty-state mono">{dataDirQuery.data ?? '…'}</p>
        <p className="composer-hint">
          任务证据、截图和报告保存在此目录；模型配置文件位于{' '}
          <span className="mono">{config.config_file}</span>。
        </p>
        <div className="composer-actions">
          <button
            type="button"
            className="plain-button"
            disabled={revealMutation.isPending}
            onClick={() => revealMutation.mutate()}
          >
            <FolderOpen size={14} aria-hidden /> 在 Finder 中打开
          </button>
          {revealMutation.isError ? (
            <p className="error-detail">{String(revealMutation.error)}</p>
          ) : null}
        </div>
      </section>

      {confirmingRestart ? (
        <div className="dialog-backdrop" role="presentation">
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="restart-title"
          >
            <h2 id="restart-title">重启 Runtime 使配置生效</h2>
            <div className="dialog-risk">
              <AlertTriangle size={15} aria-hidden />
              <p>
                配置已保存。当前有任务正在执行，重启 Runtime 会中断该任务。
                可以稍后在设置页重新点击「保存并重启」。
              </p>
            </div>
            {restartMutation.isError ? (
              <p className="error-detail">{String(restartMutation.error)}</p>
            ) : null}
            <div className="dialog-actions">
              <button
                type="button"
                className="plain-button"
                disabled={restartMutation.isPending}
                onClick={() => setConfirmingRestart(false)}
              >
                稍后重启
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={restartMutation.isPending}
                onClick={() => restartMutation.mutate()}
              >
                {restartMutation.isPending ? '正在重启…' : '立即重启'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
