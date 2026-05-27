/**
 * useApi — generic data-fetching hook.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useApi(getMetricHistory, [hours])
 *
 * - Fetches on mount and whenever `deps` change.
 * - Passes `...args` to the fetcher function.
 * - Returns { data, loading, error, refetch }.
 */
import { useState, useEffect, useCallback, useRef } from 'react'

export function useApi(fetcher, args = [], { initialData = null, skip = false } = {}) {
  const [data,    setData]    = useState(initialData)
  const [loading, setLoading] = useState(!skip)
  const [error,   setError]   = useState(null)

  // Prevent state updates after unmount
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  const fetch = useCallback(async () => {
    if (skip) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetcher(...args)
      if (mountedRef.current) setData(res.data)
    } catch (err) {
      if (mountedRef.current) setError(err?.response?.data?.detail || 'Request failed')
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher, skip, JSON.stringify(args)])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, error, refetch: fetch }
}
