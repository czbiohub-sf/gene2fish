import { useState, useEffect } from "react";

export function useGeneData(genes, stageMin, stageMax, anatomy) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!genes || genes.length === 0) {
      setData({});
      return;
    }

    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const body = {
          genes,
          stage_min: stageMin ?? null,
          stage_max: stageMax ?? null,
          anatomy: anatomy ?? null,
        };
        const res = await fetch("/api/genes/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [genes.join(","), stageMin, stageMax, anatomy]);

  return { data, loading, error };
}
