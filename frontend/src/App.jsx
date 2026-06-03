import { useCallback, useMemo, useState } from "react";
import { useUrlState } from "./hooks/useUrlState.js";
import { useGeneData } from "./hooks/useGeneData.js";
import { StageFilter } from "./components/StageFilter.jsx";
import { AnatomyFilter } from "./components/AnatomyFilter.jsx";
import { useAnatomyGenes } from "./hooks/useAnatomyGenes.js";
import { ComparisonPanel } from "./components/ComparisonPanel.jsx";
import { ComparisonSidebar } from "./components/ComparisonSidebar.jsx";
import { Attribution } from "./components/Attribution.jsx";

const N_IMAGE_OPTIONS = [1, 3, 6, 10];
const MAX_COMPARISON_GENES = 6;
const GENE_COLORS = ["#6e2bb8", "#514de8", "#10879a", "#ef7d22", "#2f9d68", "#c43d87"];

export default function App() {
  const [urlState, setUrlState] = useUrlState();
  const { genes, stageMin, stageMax, anatomy, nImages } = urlState;
  const [theme, setTheme] = useState("light");
  const [comparisonMaximized, setComparisonMaximized] = useState(false);

  const { data, loading, error } = useGeneData(genes, stageMin, stageMax, nImages);
  const {
    suggestions: anatomyGeneSuggestions,
    total: anatomyGeneTotal,
    loading: anatomyGeneLoading,
    error: anatomyGeneError,
  } = useAnatomyGenes(anatomy, 50);

  const addGene = useCallback(
    (symbol) => {
      const trimmed = symbol.trim();
      if (!trimmed) return;
      setUrlState((s) => ({
        ...s,
        genes: s.genes.includes(trimmed) || s.genes.length >= MAX_COMPARISON_GENES
          ? s.genes
          : [...s.genes, trimmed],
      }));
    },
    [setUrlState]
  );

  const removeGene = useCallback(
    (symbol) => {
      setUrlState((s) => ({ ...s, genes: s.genes.filter((g) => g !== symbol) }));
    },
    [setUrlState]
  );

  const clearGenes = useCallback(
    () => {
      setUrlState((s) => ({ ...s, genes: [] }));
      setComparisonMaximized(false);
    },
    [setUrlState]
  );

  const setStageRange = useCallback(
    (min, max) => {
      setUrlState((s) => ({ ...s, stageMin: min, stageMax: max }));
    },
    [setUrlState]
  );

  const setAnatomy = useCallback(
    (term) => {
      setUrlState((s) => ({ ...s, anatomy: term }));
    },
    [setUrlState]
  );

  const setNImages = useCallback(
    (n) => {
      setUrlState((s) => ({ ...s, nImages: n }));
    },
    [setUrlState]
  );

  const stageCount = useMemo(() => {
    const stages = new Set();
    for (const symbol of genes) {
      for (const img of data[symbol] || []) {
        if (img.stage_begin_hours != null) stages.add(img.stage_begin_hours);
      }
    }
    return stages.size;
  }, [genes, data]);

  const geneMetaBySymbol = useMemo(() => {
    const result = {};
    genes.forEach((symbol, index) => {
      result[symbol] = {
        color: GENE_COLORS[index % GENE_COLORS.length],
        imageCount: (data[symbol] || []).length,
      };
    });
    return result;
  }, [genes, data]);

  return (
    <div className="app-root" data-theme={theme}>
      <header className="app-header">
        <div className="app-shell app-header-bar">
          <a className="brand" href="/" aria-label="gene2fish home">
            <span className="brand-icon" aria-hidden="true" />
            <h1>Gene2fish</h1>
          </a>
          <nav className="header-links" aria-label="Primary">
            <a href="https://github.com/czbiohub-sf/gene2fish#readme" target="_blank" rel="noopener noreferrer">
              About
            </a>
            <a href="https://zfin.org" target="_blank" rel="noopener noreferrer">
              ZFIN <span aria-hidden="true">↗</span>
            </a>
            <button
              className="theme-toggle"
              type="button"
              title="Toggle theme"
              aria-label="Toggle theme"
              onClick={() => setTheme((current) => current === "light" ? "dark" : "light")}
            >
              {theme === "light" ? "◐" : "○"}
            </button>
          </nav>
        </div>
      </header>

      <main className="app-main app-shell">
        <div className={`comparison-workspace${comparisonMaximized ? " comparison-workspace-maximized" : ""}`}>
          <ComparisonSidebar
            genes={genes}
            geneMetaBySymbol={geneMetaBySymbol}
            maxGenes={MAX_COMPARISON_GENES}
            anatomy={anatomy}
            suggestedGenes={anatomyGeneSuggestions}
            suggestedTotal={anatomyGeneTotal}
            suggestionsLoading={anatomyGeneLoading}
            suggestionsError={anatomyGeneError}
            onAddGene={addGene}
            onRemoveGene={removeGene}
            onClearGenes={clearGenes}
          />
          <div className="comparison-content">
            <section className="control-card filters-card" aria-labelledby="filters-title">
              <h2 id="filters-title" className="visually-hidden">Filters</h2>
              {(loading || error) && (
                <span className={`request-status${error ? " error" : ""}`}>
                  {error ? `Error: ${error}` : "Loading…"}
                </span>
              )}
              <div className="filters-grid">
                <StageFilter
                  stageMin={stageMin}
                  stageMax={stageMax}
                  onChange={setStageRange}
                />
                <AnatomyFilter value={anatomy} onChange={setAnatomy} />
                <div className="n-images-toggle">
                  <span className="n-images-label">Images per cell</span>
                  <div className="n-images-buttons">
                    {N_IMAGE_OPTIONS.map((n) => (
                      <button
                        key={n}
                        className={`n-images-btn${(nImages ?? 1) === n ? " active" : ""}`}
                        onClick={() => setNImages(n)}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <ComparisonPanel
              genes={genes}
              data={data}
              geneMetaBySymbol={geneMetaBySymbol}
              stageCount={stageCount}
              anatomy={anatomy}
              nImages={nImages ?? 1}
              matchedGeneCount={anatomyGeneTotal}
              isMaximized={comparisonMaximized}
              onToggleMaximize={() => setComparisonMaximized((current) => !current)}
              onRemoveGene={removeGene}
              onAddGene={addGene}
              onSetAnatomy={setAnatomy}
            />
          </div>
        </div>
      </main>

      <Attribution />
    </div>
  );
}
