import { useEffect, useMemo, useState } from "react";
import { useAnatomyGenes } from "../hooks/useAnatomyGenes.js";

const LIMIT_OPTIONS = [
  { value: 50, label: "Top 50" },
  { value: 100, label: "Top 100" },
  { value: "all", label: "All" },
];

const ALL_LIMIT = 1000;

export function AnatomySuggestedGenes({ anatomy, queriedGenes, onAddGene }) {
  const [limit, setLimit] = useState(50);

  // Reset limit when the anatomy term changes so each new term starts at Top 50.
  useEffect(() => {
    setLimit(50);
  }, [anatomy]);

  const effectiveLimit = limit === "all" ? ALL_LIMIT : limit;
  const { suggestions, total, loading, error } = useAnatomyGenes(anatomy, effectiveLimit);

  const queriedSet = useMemo(() => new Set(queriedGenes), [queriedGenes]);

  if (!anatomy) return null;
  if (!loading && suggestions.length === 0 && !error) return null;

  const showingPartial = !loading && total > suggestions.length;

  return (
    <div className="suggested-genes-wrap">
      <div className="suggested-genes-header">
        <span className="suggested-genes-title">
          Genes with expression in <strong>{anatomy}</strong>
          {!loading && total > 0 && (
            <span className="suggested-genes-count">
              {" "}({total}
              {showingPartial && (
                <span className="suggested-genes-subcount">
                  , showing {suggestions.length}
                </span>
              )}
              )
            </span>
          )}
        </span>
        <label className="suggested-genes-limit">
          Show
          <select
            value={limit}
            onChange={(e) => {
              const v = e.target.value;
              setLimit(v === "all" ? "all" : parseInt(v, 10));
            }}
          >
            {LIMIT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        {loading && <span className="suggested-genes-loading">Loading…</span>}
        {error && <span className="suggested-genes-error">Error: {error}</span>}
      </div>
      {suggestions.length > 0 && (
        <div className="suggested-genes-strip">
          {suggestions.map((s) => {
            const added = queriedSet.has(s.gene_symbol);
            return (
              <button
                key={s.gene_symbol}
                className={`suggested-gene-chip${added ? " added" : ""}`}
                disabled={added}
                onClick={() => onAddGene(s.gene_symbol)}
                title={added ? "Already added" : `${s.image_count} images`}
              >
                <span>{s.gene_symbol}</span>
                <span className="chip-count">{s.image_count}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
