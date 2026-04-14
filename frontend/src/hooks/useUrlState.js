import { useState, useEffect, useCallback, useRef } from "react";

function parseUrl() {
  const params = new URLSearchParams(window.location.search);
  const genesParam = params.get("genes");
  return {
    genes: genesParam ? genesParam.split(",").filter(Boolean) : [],
    stageMin: params.get("stage_min") ? parseFloat(params.get("stage_min")) : null,
    stageMax: params.get("stage_max") ? parseFloat(params.get("stage_max")) : null,
    anatomy: params.get("anatomy") || null,
  };
}

export function useUrlState() {
  const [state, setState] = useState(parseUrl);
  const debounceRef = useRef(null);

  const setStateAndSync = useCallback((updater) => {
    setState((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;

      // Debounced URL push
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const params = new URLSearchParams();
        if (next.genes.length) params.set("genes", next.genes.join(","));
        if (next.stageMin != null) params.set("stage_min", next.stageMin);
        if (next.stageMax != null) params.set("stage_max", next.stageMax);
        if (next.anatomy) params.set("anatomy", next.anatomy);
        const search = params.toString();
        window.history.replaceState(null, "", search ? `?${search}` : window.location.pathname);
      }, 300);

      return next;
    });
  }, []);

  // Sync from browser back/forward navigation
  useEffect(() => {
    const handler = () => setState(parseUrl());
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  return [state, setStateAndSync];
}
