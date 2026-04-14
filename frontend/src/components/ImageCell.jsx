import { useState } from "react";

export function ImageCell({ image, onClick }) {
  const [src, setSrc] = useState(image.image_url);
  const [failed, setFailed] = useState(false);

  function handleError(e) {
    if (src === image.image_url && image.image_url_fallback !== image.image_url) {
      // First failure: try the plain .jpg fallback
      setSrc(image.image_url_fallback);
    } else {
      // Second failure: show placeholder
      e.target.onerror = null;
      setFailed(true);
    }
  }

  const tooltipText = [
    image.stage_display_label,
    image.anatomy_names?.length ? image.anatomy_names.join(", ") : null,
    image.image_id,
    image.publication_id,
  ]
    .filter(Boolean)
    .join(" · ");

  if (failed) {
    return (
      <td className="image-cell">
        <div className="cell-placeholder">
          <span>Image unavailable</span>
          <a
            href={`https://zfin.org/${image.image_id}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            {image.image_id}
          </a>
        </div>
      </td>
    );
  }

  return (
    <td className="image-cell" onClick={() => onClick(image)}>
      <img
        className="cell-img"
        src={src}
        alt={`${image.gene_symbol} at ${image.stage_display_label}`}
        loading="lazy"
        onError={handleError}
      />
      <div className="cell-tooltip">{tooltipText}</div>
    </td>
  );
}
