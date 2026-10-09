import { useState, useEffect } from "react";

export function useGeneData(genes, stageMin, stageMax, nImages) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!genes || genes.length === 0) {
      setData({});
      return;
    }

    // Pending image loads are NOT flushed here (GEN-50): cells that leave the
    // grid cancel their own queued entry on unmount, and a global flush also
    // hit cells that stayed mounted across the change, leaving them empty.
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const body = {
          genes,
          stage_min: stageMin ?? null,
          stage_max: stageMax ?? null,
          // Anatomy selection drives the suggested-gene strip only. Keep the
          // open gene columns unfiltered so adding an anatomy-related gene does
          // not hide images the user already had open.
          anatomy: null,
          n_images: nImages ?? 1,
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
  }, [genes.join(","), stageMin, stageMax, nImages]);

  return { data, loading, error };
}
