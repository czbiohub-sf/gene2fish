import { useMemo, useState } from "react";
import { ImageCell } from "./ImageCell.jsx";
import { Lightbox } from "./Lightbox.jsx";
import emptyStateIllustration from "../assets/empty-state-illustration.png";

const EMPTY_STATE_EXAMPLES = [
  { label: "Example: shhb", type: "gene", value: "shhb" },
  { label: "Example: liver primordium", type: "anatomy", value: "liver primordium", gene: "nr5a2" },
  { label: "Example: prox1a", type: "gene", value: "prox1a" },
];

export function ExpressionGrid({ genes, data, onRemoveGene, onAddGene, onSetAnatomy, nImages }) {
  const [lightboxIndex, setLightboxIndex] = useState(null);

  // Collect all canonical stages that appear across any gene, sorted by begin_hours
  const rows = useMemo(() => {
    const stageMap = new Map(); // begin_hours → display_label
    for (const symbol of genes) {
      const images = data[symbol] || [];
      for (const img of images) {
        if (img.stage_begin_hours != null && !stageMap.has(img.stage_begin_hours)) {
          stageMap.set(img.stage_begin_hours, img.stage_display_label);
        }
      }
    }
    return [...stageMap.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([hours, label]) => ({ hours, label }));
  }, [genes, data]);

  // Build lookup: gene → begin_hours → ImageRecord[]
  const lookup = useMemo(() => {
    const map = {};
    for (const symbol of genes) {
      map[symbol] = {};
      for (const img of data[symbol] || []) {
        if (img.stage_begin_hours != null) {
          const h = img.stage_begin_hours;
          if (!map[symbol][h]) map[symbol][h] = [];
          map[symbol][h].push(img);
        }
      }
    }
    return map;
  }, [genes, data]);

  // Flat row-major list of every image visible in the grid, in reading order
  // (top stage → left gene → within-cell order, capped at nImages per cell).
  // Powers ←/→ navigation in the lightbox.
  const flatImages = useMemo(() => {
    const result = [];
    for (const { hours } of rows) {
      for (const symbol of genes) {
        const cellImgs = lookup[symbol]?.[hours];
        if (!cellImgs) continue;
        for (const img of cellImgs.slice(0, nImages)) {
          result.push(img);
        }
      }
    }
    return result;
  }, [rows, genes, lookup, nImages]);

  // Per-gene max image count across all stages, capped at nImages.
  // Drives column width so columns are only as wide as their actual content.
  const colMaxImages = useMemo(() => {
    const result = {};
    for (const symbol of genes) {
      let max = 1;
      for (const h of Object.keys(lookup[symbol] || {})) {
        const count = Math.min((lookup[symbol][h] || []).length, nImages);
        if (count > max) max = count;
      }
      result[symbol] = max;
    }
    return result;
  }, [lookup, genes, nImages]);

  if (genes.length === 0) {
    return (
      <section className="grid-empty" aria-labelledby="empty-state-title">
        <img
          className="grid-empty-illustration"
          src={emptyStateIllustration}
          alt=""
          aria-hidden="true"
        />
        <h2 id="empty-state-title">Search gene expression images</h2>
        <p>
          Enter a gene name and select filters to explore expression patterns in zebrafish development.
        </p>
        <div className="grid-empty-examples" aria-label="Example searches">
          {EMPTY_STATE_EXAMPLES.map((example) => (
            <button
              key={`${example.type}-${example.value}`}
              type="button"
              className={`grid-empty-example ${example.type}`}
              onClick={() => {
                if (example.type === "gene") onAddGene(example.value);
                else {
                  onSetAnatomy(example.value);
                  if (example.gene) onAddGene(example.gene);
                }
              }}
            >
              {example.label}
            </button>
          ))}
        </div>
      </section>
    );
  }

  if (rows.length === 0 && genes.length > 0) {
    return <p className="grid-empty-message">No expression images found for the selected genes and filters.</p>;
  }

  return (
    <>
      <div className="expression-grid-wrapper">
        <table className="expression-grid">
          <thead>
            <tr>
              <th className="grid-corner" />
              {genes.map((symbol) => (
                <th
                  key={symbol}
                  className="col-header"
                  style={nImages > 1
                    ? { width: `calc(var(--cell-size) * ${colMaxImages[symbol]})` }
                    : undefined}
                >
                  <div className="col-header-inner">
                    <span className="col-gene-symbol">{symbol}</span>
                    <button
                      className="col-remove-btn"
                      title={`Remove ${symbol}`}
                      onClick={() => onRemoveGene(symbol)}
                    >
                      ×
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ hours, label }) => (
              <tr key={hours}>
                <td className="row-header">{label}</td>
                {genes.map((symbol) => {
                  const imgs = lookup[symbol]?.[hours];
                  if (imgs && imgs.length > 0) {
                    return (
                      <ImageCell
                        key={symbol}
                        images={imgs}
                        nImages={nImages ?? 1}
                        colMax={colMaxImages[symbol]}
                        onClick={(img) => {
                          const idx = flatImages.findIndex((x) => x.image_id === img.image_id);
                          if (idx !== -1) setLightboxIndex(idx);
                        }}
                      />
                    );
                  }
                  return (
                    <td
                      key={symbol}
                      className="empty-cell"
                      style={nImages > 1
                        ? { width: `calc(var(--cell-size) * ${colMaxImages[symbol]})` }
                        : undefined}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {lightboxIndex != null && flatImages[lightboxIndex] && (
        <Lightbox
          image={flatImages[lightboxIndex]}
          onClose={() => setLightboxIndex(null)}
          onPrev={() => setLightboxIndex((i) => i - 1)}
          onNext={() => setLightboxIndex((i) => i + 1)}
          hasPrev={lightboxIndex > 0}
          hasNext={lightboxIndex < flatImages.length - 1}
        />
      )}
    </>
  );
}
