import { useEffect, useState } from "react";

// Fetches, for the genes currently in the comparison, which stage/anatomy
// filter options actually have images (GEN-23). Returns null when there are no
// genes OR when the request fails — callers treat null as "no constraint" so
// every option stays enabled rather than being wrongly greyed out.
export function useGeneFacets(genes) {
  const [facets, setFacets] = useState(null);
  const genesKey = genes.join(",");

  useEffect(() => {
    if (!genes || genes.length === 0) {
      setFacets(null);
      return;
    }

    let cancelled = false;

    async function fetchFacets() {
      try {
        const res = await fetch("/api/genes/facets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ genes }),
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const json = await res.json();
        if (cancelled) return;
        setFacets({
          stages: Array.isArray(json.stages) ? json.stages : [],
          anatomy: json.anatomy && typeof json.anatomy === "object" ? json.anatomy : {},
        });
      } catch {
        // Fail open: fall back to no constraint so a facets outage never hides
        // options the user could otherwise pick.
        if (!cancelled) setFacets(null);
      }
    }

    fetchFacets();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genesKey]);

  return facets;
}
