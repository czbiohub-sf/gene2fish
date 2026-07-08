import { useCallback, useState } from "react";
import { useUrlState } from "./hooks/useUrlState.js";
import { useGeneData } from "./hooks/useGeneData.js";
import { useGeneFacets } from "./hooks/useGeneFacets.js";
import { GeneInput } from "./components/GeneInput.jsx";
import { StageFilter } from "./components/StageFilter.jsx";
import { AnatomyFilter } from "./components/AnatomyFilter.jsx";
import { AnatomySuggestedGenes } from "./components/AnatomySuggestedGenes.jsx";
import { ExpressionGrid } from "./components/ExpressionGrid.jsx";
import { Attribution } from "./components/Attribution.jsx";

export default function App() {
  const [urlState, setUrlState] = useUrlState();
  const { genes, stageMin, stageMax, anatomy, nImages } = urlState;
  const [theme, setTheme] = useState("light");

  const { data, loading, error } = useGeneData(genes, stageMin, stageMax, nImages);
  // Which filter options have images for the genes in the grid — drives the
  // context-aware disabling of stage/anatomy options (GEN-23). Null when no
  // genes are present, in which case every option stays enabled.
  const facets = useGeneFacets(genes);

  const addGene = useCallback(
    (symbol) => {
      const trimmed = symbol.trim();
      if (!trimmed) return;
      setUrlState((s) => ({
        ...s,
        genes: s.genes.includes(trimmed) ? s.genes : [...s.genes, trimmed],
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

  const setStageRange = useCallback(
    (min, max) => {
      setUrlState((s) => ({ ...s, stageMin: min, stageMax: max }));
    },
    [setUrlState]
  );

  const setAnatomy = useCallback(
    (terms) => {
      const nextTerms = Array.isArray(terms) ? terms : (terms ? [terms] : []);
      setUrlState((s) => ({ ...s, anatomy: nextTerms }));
    },
    [setUrlState]
  );

  const setNImages = useCallback(
    (n) => {
      setUrlState((s) => ({ ...s, nImages: n }));
    },
    [setUrlState]
  );

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
            <a href="https://zebrahub.sf.czbiohub.org/" target="_blank" rel="noopener noreferrer">
              ZebraHub <span aria-hidden="true">↗</span>
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

      <section className="top-panel">
        <div className="app-shell control-cards">
          <section className="control-card search-card" aria-labelledby="gene-search-title">
            <h2 id="gene-search-title" className="visually-hidden">Search gene</h2>
            <GeneInput onAdd={addGene} />
          </section>

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
                stageFacets={facets?.stages ?? null}
              />
              <AnatomyFilter
                value={anatomy}
                onChange={setAnatomy}
                anatomyFacets={facets?.anatomy ?? null}
              />
            </div>
          </section>
        </div>
      </section>

      <div className="app-shell">
        <AnatomySuggestedGenes
          anatomy={anatomy}
          queriedGenes={genes}
          onAddGene={addGene}
        />
      </div>

      <main className="app-main app-shell">
        <ExpressionGrid
          genes={genes}
          data={data}
          onRemoveGene={removeGene}
          onAddGene={addGene}
          onSetAnatomy={setAnatomy}
          nImages={nImages ?? 1}
          onSetNImages={setNImages}
        />
      </main>

      <Attribution />
    </div>
  );
}
