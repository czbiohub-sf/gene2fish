import { useEffect, useState } from "react";
import { useImageQueue } from "../hooks/useImageQueue.js";

function SingleImage({ image, onClick, compact, onFail }) {
  const [src, setSrc] = useState(null); // null = waiting in queue, not yet requested
  const [failed, setFailed] = useState(false);
  const enqueue = useImageQueue();

  useEffect(() => {
    setSrc(null);
    setFailed(false);
    const dequeue = enqueue(setSrc, image.image_url);
    return dequeue; // remove from queue if unmounted before turn
  }, [image.image_url]); // re-enqueue if image changes

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

  if (!src) {
    return (
      <div
        className={`single-image-placeholder${compact ? " compact" : ""}`}
        title={[
          image.stage_display_label,
          image.anatomy_names?.length ? image.anatomy_names.join(", ") : null,
          image.image_id,
        ].filter(Boolean).join(" · ")}
      />
    );
  }

  return (
    <img
      className={`cell-img${compact ? " compact" : ""}`}
      src={src}
      alt={`${image.gene_symbol} at ${image.stage_display_label}`}
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

  useEffect(() => {
    setFailed(false);
  }, [image.image_id]);

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

export function ImageCell({ images, nImages, colMax, onClick }) {
  const n = nImages ?? 1;
  const displayImages = images.slice(0, n);
  const effectiveColMax = colMax ?? n;

  if (n === 1) {
    return <SingleCell image={displayImages[0]} onClick={onClick} />;
  }

  return (
    <td
      className="image-cell multi"
      style={{ "--n": effectiveColMax }}
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
