import { useRef, useState, useEffect } from "react";
import { resetQueue } from "./useImageQueue.js";

export function useGeneData(genes, stageMin, stageMax, nImages) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const previousSearchKeyRef = useRef(null);

  useEffect(() => {
    if (!genes || genes.length === 0) {
      setData({});
      previousSearchKeyRef.current = null;
      resetQueue();
      return;
    }

    let cancelled = false;
    // Changing images-per-cell should not flush queued image loads; only a new
    // gene/stage search should cancel the previous queue.
    const searchKey = JSON.stringify({ genes, stageMin, stageMax });
    if (previousSearchKeyRef.current !== searchKey) {
      resetQueue(); // flush pending loads only for a new gene/stage search
      previousSearchKeyRef.current = searchKey;
    }

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
