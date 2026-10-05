// Images load from our S3 mirror of the ZFIN-provided Thisse package through
// the backend image proxy (/api/image-proxy). The proxy serves only what is in
// that package and answers 404 for anything else; it never fetches from ZFIN
// itself. On a miss (or a mirror outage) the browser loads the image straight
// from zfin.org instead: a plain hotlink, which ZFIN permits for the Thisse
// images and prefers for its own usage statistics (GEN-22, GEN-45).
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

// Sources to try, in order, for an image whose variant URLs are given best
// first: each variant from our mirror, then the same variants hotlinked from
// zfin.org. URLs the proxy leaves unchanged appear only once.
//
// The proxy itself retries an `_annot.jpg` URL as its plain `.jpg` against the
// mirror, so that plain variant is not requested through the proxy again; it is
// still hotlinked. Any other fallback (e.g. `_medium.jpg` -> `.jpg`) is not
// covered by the proxy and keeps its own proxied candidate.
const ANNOT_SUFFIX = "_annot.jpg";

function proxyServesPlainVariant(primary, url) {
  return primary.endsWith(ANNOT_SUFFIX) && url === `${primary.slice(0, -ANNOT_SUFFIX.length)}.jpg`;
}

export function imageSrcCandidates(...urls) {
  const present = urls.filter(Boolean);
  const mirrored = present.filter((url, i) => i === 0 || !proxyServesPlainVariant(present[0], url));
  return [...new Set([...mirrored.map(proxiedImageSrc), ...present])];
}

// The candidate to try after `current` failed to load, or undefined when none are left.
export function nextImageSrc(candidates, current) {
  const index = candidates.indexOf(current);
  return index === -1 ? undefined : candidates[index + 1];
}
