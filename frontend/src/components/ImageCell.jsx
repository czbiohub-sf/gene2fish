import { useState } from "react";

function SingleImage({ image, onClick, compact, onFail }) {
  const [src, setSrc] = useState(image.image_url);
  const [failed, setFailed] = useState(false);

  function handleError(e) {
    if (src === image.image_url && image.image_url_fallback !== image.image_url) {
      setSrc(image.image_url_fallback);
    } else {
      e.target.onerror = null;
      setFailed(true);
      onFail?.();
    }
  }

  if (failed) return null;

  return (
    <img
      className={`cell-img${compact ? " compact" : ""}`}
      src={src}
      alt={`${image.gene_symbol} at ${image.stage_display_label}`}
      loading="lazy"
      onError={handleError}
      onClick={(e) => { e.stopPropagation(); onClick(image); }}
      title={[
        image.stage_display_label,
        image.anatomy_names?.length ? image.anatomy_names.join(", ") : null,
        image.image_id,
      ].filter(Boolean).join(" · ")}
    />
  );
}

function SingleCell({ image, onClick }) {
  const [failed, setFailed] = useState(false);

  const tooltipText = [
    image.stage_display_label,
    image.anatomy_names?.length ? image.anatomy_names.join(", ") : null,
    image.image_id,
    image.publication_id,
  ].filter(Boolean).join(" · ");

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
      <SingleImage image={image} onClick={onClick} compact={false} onFail={() => setFailed(true)} />
      <div className="cell-tooltip">{tooltipText}</div>
    </td>
  );
}

export function ImageCell({ images, nImages, onClick }) {
  const n = nImages ?? 1;
  const displayImages = images.slice(0, n);

  if (n === 1) {
    return <SingleCell image={displayImages[0]} onClick={onClick} />;
  }

  return (
    <td
      className="image-cell multi"
      style={{ "--n": n }}
    >
      <div className="image-cell-inner multi">
        {displayImages.map((img) => (
          <SingleImage
            key={img.image_id}
            image={img}
            onClick={onClick}
            compact={true}
          />
        ))}
      </div>
    </td>
  );
}
