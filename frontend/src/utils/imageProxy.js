// Route ZFIN image hotlinks through the backend image proxy (/api/image-proxy)
// so images are served from our own cloud — an S3 mirror of ZFIN, with a
// live-ZFIN fallback on the backend — instead of loading directly from
// zfin.org. This keeps images loading during temporary ZFIN outages (GEN-22).
//
// Non-ZFIN, relative, or malformed URLs are returned unchanged.
export function proxiedImageSrc(src) {
  if (!src) return src;
  try {
    const url = new URL(src);
    if (url.hostname === "zfin.org" && url.pathname.startsWith("/imageLoadUp/")) {
      return `/api/image-proxy?url=${encodeURIComponent(src)}`;
    }
  } catch {
    // Keep relative or malformed URLs unchanged so the normal image error path handles them.
  }
  return src;
}
