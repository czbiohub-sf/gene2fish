import { useEffect, useMemo, useState } from "react";

const DEFAULT_SUGGESTED_GENES = [
  { gene_symbol: "nr5a2" },
  { gene_symbol: "prox1a" },
  { gene_symbol: "npm1a" },
  { gene_symbol: "efnb1" },
  { gene_symbol: "polr3gla" },
  { gene_symbol: "isl2a" },
  { gene_symbol: "angptl3" },
  { gene_symbol: "vtnb" },
  { gene_symbol: "sox17" },
];

export function ComparisonSidebar({
  genes,
  geneMetaBySymbol,
  maxGenes,
  anatomy,
  suggestedGenes,
  suggestedTotal,
  suggestionsLoading,
  suggestionsError,
  onAddGene,
  onRemoveGene,
  onClearGenes,
}) {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/genes/search?q=${encodeURIComponent(trimmed)}`);
        const json = res.ok ? await res.json() : [];
        if (!cancelled) setSearchResults(json.map((gene_symbol) => ({ gene_symbol })));
      } catch {
        if (!cancelled) setSearchResults([]);
      } finally {
        if (!cancelled) setSearchLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const queriedSet = useMemo(() => new Set(genes), [genes]);
  const hasSearch = query.trim().length > 0;
  const baseSuggestions = anatomy ? suggestedGenes : DEFAULT_SUGGESTED_GENES;
  const visibleSuggestions = hasSearch ? searchResults : baseSuggestions;
  const showSuggestionsWrap = hasSearch || suggestionsLoading || suggestionsError || visibleSuggestions.length > 0;
  const isAtLimit = genes.length >= maxGenes;

  return (
    <aside className="comparison-sidebar" aria-label="Comparison controls">
      <section className="sidebar-section selected-genes-section">
        <div className="sidebar-section-header">
          <div>
            <h2>Comparing genes</h2>
            <span>{genes.length} / {maxGenes}</span>
          </div>
          {genes.length > 0 && (
            <button className="sidebar-clear-btn" type="button" onClick={onClearGenes}>
              Clear all
            </button>
          )}
        </div>

        {genes.length === 0 ? (
          <div className="selected-genes-empty">
            <span className="selected-genes-empty-icon" aria-hidden="true">▦</span>
            <p>No genes selected</p>
            <span>Add a gene to start comparing expression patterns.</span>
          </div>
        ) : (
          <ul className="selected-gene-list" aria-label="Selected genes">
            {genes.map((symbol) => {
              const meta = geneMetaBySymbol[symbol] || {};
              return (
                <li key={symbol} className="selected-gene-row">
                  <span className="gene-color-dot" style={{ "--gene-color": meta.color }} aria-hidden="true" />
                  <span className="selected-gene-symbol">{symbol}</span>
                  <button
                    type="button"
                    className="selected-gene-remove"
                    aria-label={`Remove ${symbol}`}
                    onClick={() => onRemoveGene(symbol)}
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="sidebar-section add-genes-section">
        <h2>Add more genes</h2>
        <div className="sidebar-search">
          <input
            type="text"
            value={query}
            placeholder="Search gene..."
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search gene to add"
          />
          <span aria-hidden="true">⌕</span>
        </div>

        {showSuggestionsWrap && (
          <div className="suggested-genes-wrap sidebar-suggestions">
            {anatomy && !hasSearch && !suggestionsError && (
              <div className="suggested-genes-header">
                <span className="suggested-genes-title">
                  Genes with expression in <strong>{anatomy}</strong>
                  {suggestedTotal > 0 && <span className="suggested-genes-count"> ({suggestedTotal})</span>}
                </span>
              </div>
            )}
            {(suggestionsLoading || searchLoading) && (
              <span className="suggested-genes-loading">Loading…</span>
            )}
            {suggestionsError && (
              <span className="suggested-genes-error">Error: {suggestionsError}</span>
            )}
            {!suggestionsLoading && !searchLoading && !suggestionsError && visibleSuggestions.length === 0 && (
              <span className="suggested-genes-empty">No genes found.</span>
            )}
            {visibleSuggestions.length > 0 && (
              <div className="suggested-genes-strip">
                {visibleSuggestions.map((item) => {
                  const symbol = item.gene_symbol;
                  const added = queriedSet.has(symbol);
                  return (
                    <button
                      key={symbol}
                      className={`suggested-gene-chip${added ? " added" : ""}`}
                      disabled={added || (!added && isAtLimit)}
                      onClick={() => onAddGene(symbol)}
                      title={added ? "Already added" : isAtLimit ? `Up to ${maxGenes} genes can be compared` : `${item.image_count ?? "Add"} images`}
                    >
                      <span>{symbol}</span>
                      <span className="chip-count" aria-hidden="true">{added ? "✓" : "+"}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>

      <div className="sidebar-tip-card">
        <span aria-hidden="true">☼</span>
        <p><strong>Tip:</strong> Add up to {maxGenes} genes to compare. Columns are scrollable.</p>
      </div>
    </aside>
  );
}
