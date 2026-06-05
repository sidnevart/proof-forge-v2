'use client'

import { useEffect, useRef, useCallback } from 'react'

export type SSEEvent = {
  type: string
  data: Record<string, unknown>
}

type SSEHandler = (event: SSEEvent) => void

export function useSSEStream(
  url: string | null,
  onEvent: SSEHandler,
  options: { maxRetries?: number; retryDelay?: number } = {}
) {
  const { maxRetries = 3, retryDelay = 2000 } = options
  const esRef = useRef<EventSource | null>(null)
  const retriesRef = useRef(0)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (!url) return

    const es = new EventSource(url)
    esRef.current = es

    const handleMessage = (type: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        onEventRef.current({ type, data })
      } catch {
        // ignore malformed events
      }
    }

    for (const eventType of ['phase_change', 'token', 'task_ready', 'progress', 'complete', 'error']) {
      es.addEventListener(eventType, handleMessage(eventType) as EventListener)
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      if (retriesRef.current < maxRetries) {
        retriesRef.current += 1
        setTimeout(connect, retryDelay * retriesRef.current)
      }
    }

    // EventSource automatically handles reconnection for named events
    // but we also listen for complete to close cleanly
    es.addEventListener('complete', () => {
      es.close()
      esRef.current = null
    })
  }, [url, maxRetries, retryDelay])

  useEffect(() => {
    retriesRef.current = 0
    connect()
    return () => {
      esRef.current?.close()
      esRef.current = null
    }
  }, [connect])
}
