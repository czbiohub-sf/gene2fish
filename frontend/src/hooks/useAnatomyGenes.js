import { useEffect, useState } from "react";

export function useAnatomyGenes(anatomy, limit) {
  const [suggestions, setSuggestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!anatomy) {
      setSuggestions([]);
      setTotal(0);
      setError(null);
      return;
    }

    let cancelled = false;

    async function fetchSuggestions() {
      setLoading(true);
      setError(null);
      try {
        const url = `/api/anatomy/${encodeURIComponent(anatomy)}/genes?limit=${limit}`;
        const res = await fetch(url);
        if (!res.ok) {
          if (res.status === 404) {
            if (!cancelled) {
              setSuggestions([]);
              setTotal(0);
            }
            return;
          }
          throw new Error(`API error: ${res.status}`);
        }
        const json = await res.json();
        if (!cancelled) {
          setSuggestions(json.genes || []);
          setTotal(json.total || 0);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchSuggestions();
    return () => {
      cancelled = true;
    };
  }, [anatomy, limit]);

  return { suggestions, total, loading, error };
}
