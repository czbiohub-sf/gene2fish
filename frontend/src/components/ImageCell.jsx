import { useEffect, useState } from "react";
import { useImageQueue } from "../hooks/useImageQueue.js";
import { proxiedImageSrc } from "../utils/imageProxy.js";

function SingleImage({ image, onClick, compact, onFail }) {
  const [src, setSrc] = useState(null); // null = waiting in queue, not yet requested
  const [failed, setFailed] = useState(false);
  const enqueue = useImageQueue();

  // Load through the backend proxy (our S3 mirror, with live-ZFIN fallback) so
  // images keep loading during temporary ZFIN outages (GEN-22).
  //
  // The grid serves ZFIN's medium variant (~15KB, 500x374) instead of the
  // full-res image (~377KB): a comparison view of N images then transfers
  // ~N*15 KB rather than ~N*377 KB, which is what made the grid slow to load,
  // while 500px stays sharp at the ~172px cell size (even on HiDPI). The tiny
  // 86x64 thumbnail looked blurry upscaled into the cell (GEN-36). The lightbox
  // still loads full-res. If the medium variant is missing we fall back to the
  // plain full-res image.
  const primarySrc = proxiedImageSrc(image.image_medium_url);
  const fallbackSrc = proxiedImageSrc(image.image_url_fallback);

  useEffect(() => {
    setSrc(null);
    setFailed(false);
    const dequeue = enqueue(setSrc, primarySrc);
    return dequeue; // remove from queue if unmounted before turn
  }, [image.image_medium_url]); // re-enqueue if image changes

  function handleError(e) {
    if (src === primarySrc && fallbackSrc !== primarySrc) {
      setSrc(fallbackSrc);
    } else {
      e.target.onerror = null;
      setFailed(true);
      onFail?.();
    }
  }

  if (failed) return null;

  if (!src) {
    return (
      <button
        type="button"
        className={`single-image-placeholder${compact ? " compact" : ""}`}
        aria-label={`${image.gene_symbol} at ${image.stage_display_label}`}
        onClick={(e) => { e.stopPropagation(); onClick(image); }}
        title={[
          image.stage_display_label,
          image.anatomy_terms?.length ? image.anatomy_terms.map((a) => a.anatomy_name).join(", ") : null,
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
        image.anatomy_terms?.length ? image.anatomy_terms.map((a) => a.anatomy_name).join(", ") : null,
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
    image.anatomy_terms?.length ? image.anatomy_terms.map((a) => a.anatomy_name).join(", ") : null,
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
