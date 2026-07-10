// Image loading strategy (GEN-27).
//
// Images render directly from our public S3 mirror — no backend proxy, no auth,
// so it works identically in local/staging/prod. Each image carries a
// preference chain the UI walks on error:
//   image_url          → S3 mirror, annotated variant (preferred)
//   image_url_fallback → S3 mirror, plain variant (present for every image)
//   image_url_zfin     → live ZFIN, plain variant (last resort: not-yet-mirrored)

// Ordered, de-duplicated list of sources to try for an image.
export function imageSources(image) {
  return [image.image_url, image.image_url_fallback, image.image_url_zfin]
    .filter(Boolean)
    .filter((url, i, all) => all.indexOf(url) === i);
}

// Route an image URL through the backend proxy (/api/image-proxy). Used ONLY by
// the PNG export, where a cross-origin <img> would taint the export canvas — the
// proxy returns the bytes same-origin. Recognises both our S3 mirror URLs and
// ZFIN imageLoadUp URLs; anything else is returned unchanged.
export function proxiedImageSrc(src) {
  if (!src) return src;
  try {
    const url = new URL(src);
    const isZfin = url.hostname === "zfin.org" && url.pathname.startsWith("/imageLoadUp/");
    const isMirror =
      url.hostname.endsWith(".amazonaws.com") && url.pathname.includes("/imageLoadUp/");
    if (isZfin || isMirror) {
      return `/api/image-proxy?url=${encodeURIComponent(src)}`;
    }
  } catch {
    // Keep relative or malformed URLs unchanged so the normal image error path handles them.
  }
  return src;
}
