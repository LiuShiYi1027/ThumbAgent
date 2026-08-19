import { useEffect, useState } from 'react'
import { ImageOff } from 'lucide-react'

import { getScreenshotContent } from '../api/client'

/**
 * Render one stored screenshot artifact. The PNG travels through the
 * token-gated IPC bridge as base64 and lives only in an in-memory blob URL,
 * revoked on change/unmount.
 */
export function ScreenshotImage({
  artifactId,
  alt,
}: {
  artifactId: string
  alt: string
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setUrl(null)
    setError(null)
    getScreenshotContent(artifactId)
      .then((blob) => {
        if (cancelled) {
          return
        }
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(String(loadError))
        }
      })
    return () => {
      cancelled = true
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [artifactId])

  if (error) {
    return (
      <div className="screenshot-placeholder screenshot-error">
        <ImageOff size={18} aria-hidden />
        <span>截图加载失败：{error}</span>
      </div>
    )
  }
  if (!url) {
    return <div className="screenshot-placeholder">截图加载中…</div>
  }
  return <img className="device-screenshot" src={url} alt={alt} />
}
