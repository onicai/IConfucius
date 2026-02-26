import { useState, useEffect, useCallback, useRef } from "react";

const _clientCache = new Map();

export function useFetch(fetchFn, deps = [], { cacheKey } = {}) {
  const cached = cacheKey ? _clientCache.get(cacheKey) : undefined;
  const [data, setData] = useState(cached ?? null);
  const [loading, setLoading] = useState(cached == null);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const refetch = useCallback(() => {
    if (!data) setLoading(true);
    setError(null);
    fetchFn()
      .then((d) => {
        if (!mountedRef.current) return;
        setData(d);
        if (cacheKey) _clientCache.set(cacheKey, d);
      })
      .catch((e) => {
        if (!mountedRef.current) return;
        setError(e.message);
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}

export function clearClientCache(key) {
  if (key) _clientCache.delete(key);
  else _clientCache.clear();
}
