import { useEffect } from "react";
import { imageSources } from "../utils/imageProxy.js";

function zfinUrl(id) {
  return `https://zfin.org/${id}`;
}

function zfinQuickSearchUrl(query) {
  return `https://www.zfin.org/action/quicksearch/prototype?q=${encodeURIComponent(query)}`;
}

function ncbiSearchUrl(query) {
  return `https://www.ncbi.nlm.nih.gov/search/all/?term=${encodeURIComponent(query)}`;
}

function uniprotQueryUrl(id) {
  return `https://www.uniprot.org/uniparc?query=(dbid:${encodeURIComponent(id)})`;
}

export function Lightbox({ image, onClose, onPrev, onNext, hasPrev, hasNext }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft" && hasPrev) onPrev();
      else if (e.key === "ArrowRight" && hasNext) onNext();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, onPrev, onNext, hasPrev, hasNext]);

  if (!image) return null;

  function stopAndCall(fn) {
    return (e) => {
      e.stopPropagation();
      fn();
    };
  }

  return (
    <div className="lightbox-overlay" onClick={onClose}>
      <button
        className="lightbox-nav lightbox-nav-prev"
        onClick={stopAndCall(onPrev)}
        disabled={!hasPrev}
        aria-label="Previous image"
      >
        ‹
      </button>
      <div className="lightbox-inner" onClick={(e) => e.stopPropagation()}>
        <div className="lightbox-header">
          <span className="lightbox-title">{image.gene_symbol}</span>
          <button className="lightbox-close" onClick={onClose}>×</button>
        </div>
        <div className="lightbox-body">
          <div className="lightbox-image-col">
            <img
              // key forces a fresh element per image so the attempt counter and
              // any display:none from a prior image are reset on navigation.
              key={image.image_id}
              className="lightbox-img"
              // Loaded directly from the public S3 mirror, walking the source
              // chain on error: S3 annotated → S3 plain → live ZFIN (GEN-27).
              src={imageSources(image)[0]}
              alt={`${image.gene_symbol} expression`}
              onError={(e) => {
                const img = e.target;
                const sources = imageSources(image);
                const next = Number(img.dataset.attempt || "0") + 1;
                if (next < sources.length) {
                  img.dataset.attempt = String(next);
                  img.src = sources[next];
                } else {
                  img.style.display = "none";
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
            <GeneMeta image={image} />
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
            {(image.est_symbol || image.est_id) && (
              <div className="meta-group">
                <div className="meta-label">Clone / probe</div>
                <div className="meta-value mono">
                  {image.est_symbol && (
                    <ExternalLink href={zfinQuickSearchUrl(image.est_symbol)}>
                      {image.est_symbol}
                    </ExternalLink>
                  )}
                  {image.est_id && (
                    <span className="meta-secondary">
                      <ExternalLink href={zfinUrl(image.est_id)}>{image.est_id}</ExternalLink>
                    </span>
                  )}
                </div>
              </div>
            )}
            <MetaGroup label="Probe quality" value={image.probe_quality} />
            <MetaGroup label="Fish line" value={image.fish_name} />
            {image.publication_id && (
              <div className="meta-group">
                <div className="meta-label">Publication</div>
                <div className="meta-value mono">
                  <a
                    href={zfinUrl(image.publication_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {image.publication_id}
                  </a>
                </div>
              </div>
            )}
            {image.pubmed_id && (
              <div className="meta-group">
                <div className="meta-label">PubMed</div>
                <div className="meta-value mono">
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/${image.pubmed_id}/`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {image.pubmed_id}
                  </a>
                </div>
              </div>
            )}
            <div className="meta-group">
              <div className="meta-label">Image ID</div>
              <div className="meta-value mono">
                <ExternalLink href={zfinUrl(image.image_id)}>{image.image_id}</ExternalLink>
              </div>
            </div>
            {image.human_orthologs?.length > 0 && (
              <div className="meta-group">
                <div className="meta-label">Human orthologs</div>
                <ul className="meta-list">
                  {image.human_orthologs.filter((o) => o.human_symbol).map((o) => (
                    <li key={o.human_symbol} className="meta-tag">
                      <ExternalLink href={ncbiSearchUrl(o.human_symbol)}>{o.human_symbol}</ExternalLink>
                    </li>
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
                    <li key={u} className="meta-tag">
                      <ExternalLink href={uniprotQueryUrl(u)}>{u}</ExternalLink>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
      <button
        className="lightbox-nav lightbox-nav-next"
        onClick={stopAndCall(onNext)}
        disabled={!hasNext}
        aria-label="Next image"
      >
        ›
      </button>
    </div>
  );
}

function ExternalLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

function GeneMeta({ image }) {
  const geneName = image.gene_name || image.gene_symbol;
  if (!geneName && !image.gene_id) return null;

  return (
    <div className="meta-group">
      <div className="meta-label">Gene</div>
      <div className="meta-value">
        {geneName && <div className="meta-primary">{geneName}</div>}
        {image.gene_id && (
          <div className="meta-value mono">
            <ExternalLink href={zfinUrl(image.gene_id)}>{image.gene_id}</ExternalLink>
          </div>
        )}
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
