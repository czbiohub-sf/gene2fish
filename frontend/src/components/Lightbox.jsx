import { useEffect } from "react";

export function Lightbox({ image, onClose }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  if (!image) return null;

  return (
    <div className="lightbox-overlay" onClick={onClose}>
      <div className="lightbox-inner" onClick={(e) => e.stopPropagation()}>
        <div className="lightbox-header">
          <span className="lightbox-title">{image.gene_symbol}</span>
          <button className="lightbox-close" onClick={onClose}>×</button>
        </div>
        <div className="lightbox-body">
          <div className="lightbox-image-col">
            <img
              className="lightbox-img"
              src={image.image_url}
              alt={`${image.gene_symbol} expression`}
              onError={(e) => {
                if (e.target.src !== image.image_url_fallback) {
                  e.target.src = image.image_url_fallback;
                } else {
                  e.target.style.display = "none";
                }
              }}
            />
            <div>
              <a
                className="lightbox-zfin-link"
                href={`https://zfin.org/${image.image_id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                View on ZFIN ↗
              </a>
            </div>
          </div>
          <div className="lightbox-meta-col">
            <MetaGroup label="Stage" value={image.stage_display_label} />
            <MetaGroup label="Image preparation" value={image.image_preparation} />
            {image.anatomy_names?.length > 0 && (
              <div className="meta-group">
                <div className="meta-label">Anatomy</div>
                <ul className="meta-list">
                  {image.anatomy_names.map((a) => (
                    <li key={a} className="meta-tag">{a}</li>
                  ))}
                </ul>
              </div>
            )}
            <MetaGroup label="EST / probe" value={image.est_symbol} />
            <MetaGroup label="Probe quality" value={image.probe_quality} />
            <MetaGroup label="Fish line" value={image.fish_name} />
            <MetaGroup label="Publication" value={image.publication_id} mono />
            {image.pubmed_id && (
              <MetaGroup label="PubMed" value={image.pubmed_id} mono />
            )}
            <MetaGroup label="Image ID" value={image.image_id} mono />
            {image.human_orthologs?.length > 0 && (
              <div className="meta-group">
                <div className="meta-label">Human orthologs</div>
                <ul className="meta-list">
                  {image.human_orthologs.map((o) => (
                    <li key={o.human_symbol} className="meta-tag">{o.human_symbol}</li>
                  ))}
                </ul>
              </div>
            )}
            {image.disease_associations?.length > 0 && (
              <div className="meta-group">
                <div className="meta-label">Disease associations</div>
                <ul className="meta-list">
                  {image.disease_associations.map((d) => (
                    <li key={d.do_term_id} className="meta-tag">{d.do_term_name}</li>
                  ))}
                </ul>
              </div>
            )}
            {image.uniprot_ids?.length > 0 && (
              <div className="meta-group">
                <div className="meta-label">UniProt</div>
                <ul className="meta-list">
                  {image.uniprot_ids.map((u) => (
                    <li key={u} className="meta-tag">{u}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetaGroup({ label, value, mono }) {
  if (!value) return null;
  return (
    <div className="meta-group">
      <div className="meta-label">{label}</div>
      <div className={`meta-value${mono ? " mono" : ""}`}>{value}</div>
    </div>
  );
}
