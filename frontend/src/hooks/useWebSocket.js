/**
 * useWebSocket — stable WebSocket hook with exponential-backoff reconnection.
 *
 * BUG FIX vs original: handlers were an inline object literal, so their
 * reference changed on every render → connect() was recreated → useEffect
 * re-ran → the socket reconnected on every render.
 *
 * FIX: store handlers in a ref. The ref is updated on every render but
 * never causes the connect callback or the useEffect to re-run.
 */
import { useEffect, useRef, useCallback } from 'react'

const WS_URL     = 'ws://localhost:8000/ws'
const MAX_RETRIES = 12

export function useWebSocket(handlers = {}) {
  // ── Stable ref: always holds the latest handlers without triggering re-renders
  const handlersRef = useRef(handlers)
  useEffect(() => { handlersRef.current = handlers })   // sync every render, no dep array

  const wsRef           = useRef(null)
  const retriesRef      = useRef(0)
  const pingTimerRef    = useRef(null)
  const reconnectRef    = useRef(null)

  const connect = useCallback(() => {
    // Don't stack connections
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      retriesRef.current = 0
      // Client-side keepalive ping every 18 s (below server's 20 s cull window)
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 18_000)
      handlersRef.current.onOpen?.()
    }

    ws.onmessage = ({ data }) => {
      try {
        const msg = JSON.parse(data)
        switch (msg.type) {
          case 'metric':  handlersRef.current.onMetric?.(msg.data);  break
          case 'anomaly': handlersRef.current.onAnomaly?.(msg.data); break
          case 'ping':    ws.send('pong');                            break  // server heartbeat
          case 'pong':    break                                              // ack
        }
      } catch {
        // non-JSON frames (e.g. plain 'pong') — ignore silently
      }
    }

    ws.onerror = () => handlersRef.current.onError?.()

    ws.onclose = () => {
      clearInterval(pingTimerRef.current)
      handlersRef.current.onClose?.()

      if (retriesRef.current >= MAX_RETRIES) return

      // Exponential backoff: 1s → 2 → 4 → 8 → … capped at 30 s
      const delay = Math.min(1_000 * 2 ** retriesRef.current, 30_000)
      retriesRef.current++
      reconnectRef.current = setTimeout(connect, delay)
    }
  }, [])  // ← empty: connect is now truly stable

  useEffect(() => {
    connect()
    return () => {
      clearInterval(pingTimerRef.current)
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  // Expose the socket ref so callers can inspect readyState if needed
  return wsRef
}
