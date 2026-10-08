// The ZFIN-approved attribution wording, single-sourced for every surface that
// shows it: the page footer (components/Attribution.jsx) renders it with a
// hyperlink and italics, and the PNG export credit
// (utils/exportExpressionTable.js) uses the joined plain text. The split points
// exist so the footer can wrap "ZFIN (zfin.org)" in a link and "in situ" in
// <em> without duplicating the sentences.
export const PROVIDED_BY_PREFIX = "Images and image data provided by";
export const ZFIN_LABEL = "ZFIN (zfin.org)";
export const THISSE_BEFORE = "Thisse et al. high-throughput";
export const THISSE_EM = "in situ";
export const THISSE_AFTER = "hybridization data.";
export const LICENSE_LABEL = "CC BY 4.0";
export const LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/";

// The two sentences ZFIN approved, as plain text.
export const APPROVED_SENTENCES = `${PROVIDED_BY_PREFIX} ${ZFIN_LABEL}. ${THISSE_BEFORE} ${THISSE_EM} ${THISSE_AFTER}`;
