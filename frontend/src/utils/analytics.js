const IMAGE_VIEW_EVENT = "Image View";

/**
 * Record an intentional full-size image view in Plausible.
 *
 * Keep this call in user-interaction handlers rather than React effects: an
 * image becoming visible because of a render, preload, retry, or StrictMode
 * remount is not a new intentional view.
 */
export function trackImageView(image) {
  if (typeof window.plausible !== "function") return;

  const props = {
    image_id: image.image_id,
    gene_symbol: image.gene_symbol,
    stage: image.stage_display_label,
    publication_id: image.publication_id,
  };

  // Plausible displays missing values as `(none)`. Omit optional metadata that
  // the API did not provide instead of sending null or undefined explicitly.
  for (const [key, value] of Object.entries(props)) {
    if (value == null) delete props[key];
  }

  window.plausible(IMAGE_VIEW_EVENT, { props });
}
