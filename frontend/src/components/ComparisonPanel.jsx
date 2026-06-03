import { ExpressionGrid } from "./ExpressionGrid.jsx";

export function ComparisonPanel({
  genes,
  data,
  geneMetaBySymbol,
  stageCount,
  anatomy,
  nImages,
  matchedGeneCount,
  isMaximized,
  onToggleMaximize,
  onRemoveGene,
  onAddGene,
  onSetAnatomy,
}) {
  if (genes.length === 0) {
    return (
      <section className="comparison-panel comparison-panel-empty">
        <ExpressionGrid
          genes={genes}
          data={data}
          onRemoveGene={onRemoveGene}
          onAddGene={onAddGene}
          onSetAnatomy={onSetAnatomy}
          nImages={nImages}
          geneMetaBySymbol={geneMetaBySymbol}
        />
      </section>
    );
  }

  const geneSummary = genes.length === 1 ? "1 selected gene" : `${genes.length} selected genes`;
  const stageSummary = stageCount === 1 ? "1 developmental stage" : `${stageCount} developmental stages`;

  return (
    <section className={`comparison-panel${isMaximized ? " maximized" : ""}`} aria-labelledby="comparison-title">
      <div className="comparison-panel-header">
        <div className="comparison-heading-group">
          <div className="comparison-title-row">
            <h2 id="comparison-title">
              Expression comparison
              {anatomy && (
                <>
                  {" "}in <span>{anatomy}</span>
                </>
              )}
            </h2>
            {anatomy && matchedGeneCount > 0 && (
              <span className="comparison-match-badge">{matchedGeneCount} genes match your filters</span>
            )}
          </div>
          <p className="comparison-summary">
            Comparing {geneSummary} across {stageSummary} • {nImages} images per cell
          </p>
        </div>
        <button className="comparison-maximize-btn" type="button" onClick={onToggleMaximize}>
          <span aria-hidden="true">{isMaximized ? "↙" : "↗"}</span>
          {isMaximized ? "Exit maximize" : "Maximize"}
        </button>
      </div>

      <div className="comparison-grid-region">
        <ExpressionGrid
          genes={genes}
          data={data}
          onRemoveGene={onRemoveGene}
          onAddGene={onAddGene}
          onSetAnatomy={onSetAnatomy}
          nImages={nImages}
          geneMetaBySymbol={geneMetaBySymbol}
        />
      </div>
    </section>
  );
}
