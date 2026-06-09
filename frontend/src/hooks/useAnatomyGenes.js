import { useEffect, useState } from "react";

export function useAnatomyGenes(anatomy, limit) {
  const anatomyTerms = Array.isArray(anatomy) ? anatomy : (anatomy ? [anatomy] : []);
  const anatomyKey = anatomyTerms.join("\n");
  const [suggestions, setSuggestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (anatomyTerms.length === 0) {
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
        const url = anatomyTerms.length === 1
          ? `/api/anatomy/${encodeURIComponent(anatomyTerms[0])}/genes?limit=${limit}`
          : `/api/anatomy/genes?${new URLSearchParams([
            ...anatomyTerms.map((term) => ["anatomy", term]),
            ["limit", limit],
          ]).toString()}`;
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
  }, [anatomyKey, limit]);

  return { suggestions, total, loading, error };
}
