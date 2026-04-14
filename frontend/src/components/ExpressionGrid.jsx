import { useMemo, useState } from "react";
import { ImageCell } from "./ImageCell.jsx";
import { Lightbox } from "./Lightbox.jsx";

export function ExpressionGrid({ genes, data, onRemoveGene, nImages }) {
  const [lightboxImage, setLightboxImage] = useState(null);

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

  if (genes.length === 0) {
    return (
      <p className="grid-empty">
        Enter a gene symbol above to start browsing expression images.
      </p>
    );
  }

  if (rows.length === 0 && genes.length > 0) {
    return <p className="grid-empty">No expression images found for the selected genes and filters.</p>;
  }

  return (
    <>
      <div className="expression-grid-wrapper">
        <table className="expression-grid">
          <thead>
            <tr>
              <th className="grid-corner" />
              {genes.map((symbol) => (
                <th key={symbol} className="col-header">
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
                        onClick={setLightboxImage}
                      />
                    );
                  }
                  return <td key={symbol} className="empty-cell" />;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {lightboxImage && (
        <Lightbox image={lightboxImage} onClose={() => setLightboxImage(null)} />
      )}
    </>
  );
}
