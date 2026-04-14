import { useCallback } from "react";
import { useUrlState } from "./hooks/useUrlState.js";
import { useGeneData } from "./hooks/useGeneData.js";
import { GeneInput } from "./components/GeneInput.jsx";
import { StageFilter } from "./components/StageFilter.jsx";
import { AnatomyFilter } from "./components/AnatomyFilter.jsx";
import { ExpressionGrid } from "./components/ExpressionGrid.jsx";
import { Attribution } from "./components/Attribution.jsx";

export default function App() {
  const [urlState, setUrlState] = useUrlState();
  const { genes, stageMin, stageMax, anatomy } = urlState;

  const { data, loading, error } = useGeneData(genes, stageMin, stageMax, anatomy);

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
    (term) => {
      setUrlState((s) => ({ ...s, anatomy: term }));
    },
    [setUrlState]
  );

  return (
    <div id="root">
      <header className="app-header">
        <h1>gene2image</h1>
        <div className="controls">
          <GeneInput onAdd={addGene} />
          <StageFilter
            stageMin={stageMin}
            stageMax={stageMax}
            onChange={setStageRange}
          />
          <AnatomyFilter value={anatomy} onChange={setAnatomy} />
        </div>
        {loading && (
          <div style={{ marginTop: 8, fontSize: 12, color: "#6b7280" }}>
            Loading…
          </div>
        )}
        {error && (
          <div style={{ marginTop: 8, fontSize: 12, color: "#ef4444" }}>
            Error: {error}
          </div>
        )}
      </header>

      <main className="app-main">
        <ExpressionGrid
          genes={genes}
          data={data}
          onRemoveGene={removeGene}
        />
      </main>

      <Attribution />
    </div>
  );
}
