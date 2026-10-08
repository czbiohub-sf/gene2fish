import { APPROVED_SENTENCES, LICENSE_LABEL, LICENSE_URL } from "./attribution.js";
import { proxiedImageSrc } from "./imageProxy.js";

const EXPORT_CELL_SIZE = 180;
const EXPORT_ROW_HEADER_WIDTH = 150;
const EXPORT_HEADER_HEIGHT = 58;
const EXPORT_CELL_PADDING = 8;
const EXPORT_IMAGE_GAP = 4;
const EXPORT_SCALE = 2;
const EXPORT_IMAGE_LOAD_CONCURRENCY = 6;
const EXPORT_CREDIT_PADDING = 12;
const EXPORT_CREDIT_LINE_HEIGHT = 15;
const EXPORT_CREDIT_FONT = "11px sans-serif";

function cssVar(name, fallback) {
  const root = document.querySelector(".app-root") || document.documentElement;
  const value = getComputedStyle(root).getPropertyValue(name).trim();
  return value || fallback;
}

function drawText(ctx, text, x, y, maxWidth, options = {}) {
  const {
    align = "left",
    baseline = "middle",
    color = "#111827",
    font = "13px sans-serif",
  } = options;
  ctx.save();
  ctx.fillStyle = color;
  ctx.font = font;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;

  let label = text;
  while (ctx.measureText(label).width > maxWidth && label.length > 1) {
    label = `${label.slice(0, -2)}…`;
  }
  ctx.fillText(label, x, y, maxWidth);
  ctx.restore();
}

// Credit drawn under every export. The images are Thisse et al. data under
// CC BY 4.0, and ZFIN's permission requires crediting both Thisse and ZFIN
// wherever the images are used. An exported PNG travels without the app's
// footer, so it carries the same wording (shared via utils/attribution.js)
// plus the license link and the ZFIN publications it shows.
function exportCreditText(images) {
  // Numeric-aware sort: same-date ZFIN ids with multi-digit serials would
  // misorder lexicographically (ZDB-PUB-...-22 before ...-3).
  const publications = [...new Set(images.map((image) => image.publication_id).filter(Boolean))].sort(
    (a, b) => a.localeCompare(b, "en", { numeric: true })
  );
  return [
    APPROVED_SENTENCES,
    `Licensed under ${LICENSE_LABEL} (${LICENSE_URL}).`,
    ...(publications.length ? [`ZFIN publications: ${publications.join(", ")}.`] : []),
  ].join(" ");
}

// Greedy word wrap. Unlike drawText, the credit must never be truncated.
function wrapText(ctx, text, maxWidth) {
  const lines = [];
  let line = "";
  for (const word of text.split(" ")) {
    const candidate = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(candidate).width > maxWidth) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function drawRect(ctx, x, y, width, height, fill, stroke) {
  ctx.fillStyle = fill;
  ctx.fillRect(x, y, width, height);
  ctx.strokeStyle = stroke;
  ctx.strokeRect(x, y, width, height);
}

function drawPlaceholder(ctx, x, y, width, height, text, colors) {
  drawRect(ctx, x, y, width, height, colors.empty, colors.border);
  drawText(ctx, text, x + width / 2, y + height / 2, width - 16, {
    align: "center",
    color: colors.muted,
    font: "11px sans-serif",
  });
}

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    const timeout = setTimeout(() => resolve(null), 8000);
    img.crossOrigin = "anonymous";
    img.onload = () => {
      clearTimeout(timeout);
      resolve(img);
    };
    img.onerror = () => {
      clearTimeout(timeout);
      resolve(null);
    };
    img.src = src;
  });
}

// Unlike the grid and lightbox, the export never hotlinks zfin.org: ZFIN sends no
// CORS headers, so its images can't be drawn into an exportable canvas. An image
// that isn't in our mirror exports as "Image unavailable".
async function loadBestImage(image) {
  const primary = await loadImage(proxiedImageSrc(image.image_url));
  if (primary) return primary;
  if (image.image_url_fallback && image.image_url_fallback !== image.image_url) {
    return loadImage(proxiedImageSrc(image.image_url_fallback));
  }
  return null;
}

async function preloadImages(images, onImageLoaded) {
  const loadedImages = new Map();
  let nextIndex = 0;

  async function loadNext() {
    while (nextIndex < images.length) {
      const imageIndex = nextIndex;
      nextIndex += 1;
      loadedImages.set(images[imageIndex], await loadBestImage(images[imageIndex]));
      onImageLoaded?.();
    }
  }

  const workerCount = Math.min(EXPORT_IMAGE_LOAD_CONCURRENCY, images.length);
  await Promise.all(Array.from({ length: workerCount }, loadNext));
  return loadedImages;
}

function drawImageContain(ctx, img, x, y, width, height) {
  const ratio = Math.min(width / img.naturalWidth, height / img.naturalHeight);
  const drawWidth = img.naturalWidth * ratio;
  const drawHeight = img.naturalHeight * ratio;
  const drawX = x + (width - drawWidth) / 2;
  const drawY = y + (height - drawHeight) / 2;
  ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);
}

function toBlob(canvas) {
  return new Promise((resolve, reject) => {
    try {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error("PNG export failed"));
      }, "image/png");
    } catch (err) {
      reject(err);
    }
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportFilename(genes) {
  const genePart = genes.join("-").replace(/[^a-z0-9._-]+/gi, "-").slice(0, 80);
  return `gene2fish-table-${genePart || "expression"}.png`;
}

export async function exportExpressionTablePng({ rows, genes, lookup, colMaxImages, nImages, onProgress }) {
  const colors = {
    background: cssVar("--bg-page", "#ffffff"),
    card: cssVar("--bg-card", "#ffffff"),
    empty: cssVar("--bg-empty", "#f8fafc"),
    border: cssVar("--border", "#e5e7eb"),
    text: cssVar("--text-primary", "#111827"),
    secondary: cssVar("--text-secondary", "#4b5563"),
    muted: cssVar("--text-muted", "#9ca3af"),
  };

  const exportImages = [];
  for (const { hours } of rows) {
    for (const symbol of genes) {
      exportImages.push(...(lookup[symbol]?.[hours] || []).slice(0, nImages));
    }
  }
  let completedImages = 0;
  const totalImages = exportImages.length;
  onProgress?.(0);

  function reportImageProgress() {
    completedImages += 1;
    if (totalImages > 0) {
      onProgress?.(Math.round((completedImages / totalImages) * 100));
    }
  }

  const columnWidths = genes.map((symbol) => EXPORT_CELL_SIZE * (colMaxImages[symbol] || 1));
  const width = EXPORT_ROW_HEADER_WIDTH + columnWidths.reduce((sum, w) => sum + w, 0);
  const tableHeight = EXPORT_HEADER_HEIGHT + rows.length * EXPORT_CELL_SIZE;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("PNG export failed: canvas rendering is unavailable");
  }

  // Measure the wrapped credit before sizing the canvas so it always fits.
  const creditWidth = width - 2 * EXPORT_CREDIT_PADDING;
  ctx.font = EXPORT_CREDIT_FONT;
  const creditLines = wrapText(ctx, exportCreditText(exportImages), creditWidth);
  const creditHeight = 2 * EXPORT_CREDIT_PADDING + creditLines.length * EXPORT_CREDIT_LINE_HEIGHT;
  const height = tableHeight + creditHeight;
  canvas.width = width * EXPORT_SCALE;
  canvas.height = height * EXPORT_SCALE;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const loadedImages = await preloadImages(exportImages, reportImageProgress);

  ctx.scale(EXPORT_SCALE, EXPORT_SCALE);
  ctx.fillStyle = colors.background;
  ctx.fillRect(0, 0, width, height);

  drawRect(ctx, 0, 0, EXPORT_ROW_HEADER_WIDTH, EXPORT_HEADER_HEIGHT, colors.card, colors.border);

  let x = EXPORT_ROW_HEADER_WIDTH;
  genes.forEach((symbol, index) => {
    const columnWidth = columnWidths[index];
    drawRect(ctx, x, 0, columnWidth, EXPORT_HEADER_HEIGHT, colors.card, colors.border);
    drawText(ctx, symbol, x + columnWidth / 2, EXPORT_HEADER_HEIGHT / 2, columnWidth - 24, {
      align: "center",
      color: colors.text,
      font: "700 14px monospace",
    });
    x += columnWidth;
  });

  for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
    const { hours, label } = rows[rowIndex];
    const y = EXPORT_HEADER_HEIGHT + rowIndex * EXPORT_CELL_SIZE;
    drawRect(ctx, 0, y, EXPORT_ROW_HEADER_WIDTH, EXPORT_CELL_SIZE, colors.card, colors.border);
    drawText(ctx, label, EXPORT_ROW_HEADER_WIDTH - 12, y + EXPORT_CELL_SIZE / 2, EXPORT_ROW_HEADER_WIDTH - 24, {
      align: "right",
      color: colors.secondary,
      font: "12px sans-serif",
    });

    x = EXPORT_ROW_HEADER_WIDTH;
    for (let geneIndex = 0; geneIndex < genes.length; geneIndex += 1) {
      const symbol = genes[geneIndex];
      const columnWidth = columnWidths[geneIndex];
      drawRect(ctx, x, y, columnWidth, EXPORT_CELL_SIZE, colors.background, colors.border);

      const images = (lookup[symbol]?.[hours] || []).slice(0, nImages);
      if (images.length === 0) {
        drawPlaceholder(ctx, x, y, columnWidth, EXPORT_CELL_SIZE, "", colors);
      } else {
        const innerX = x + EXPORT_CELL_PADDING / 2;
        const innerY = y + EXPORT_CELL_PADDING / 2;
        const innerWidth = columnWidth - EXPORT_CELL_PADDING;
        const innerHeight = EXPORT_CELL_SIZE - EXPORT_CELL_PADDING;
        const imageWidth = (innerWidth - EXPORT_IMAGE_GAP * (images.length - 1)) / images.length;

        for (let imageIndex = 0; imageIndex < images.length; imageIndex += 1) {
          const imgData = images[imageIndex];
          const img = loadedImages.get(imgData);
          const imageX = innerX + imageIndex * (imageWidth + EXPORT_IMAGE_GAP);
          if (img) {
            drawImageContain(ctx, img, imageX, innerY, imageWidth, innerHeight);
          } else {
            drawPlaceholder(ctx, imageX, innerY, imageWidth, innerHeight, "Image unavailable", colors);
          }
        }
      }
      x += columnWidth;
    }
  }

  drawRect(ctx, 0, tableHeight, width, creditHeight, colors.card, colors.border);
  ctx.save();
  ctx.fillStyle = colors.secondary;
  ctx.font = EXPORT_CREDIT_FONT;
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  creditLines.forEach((line, index) => {
    const y = tableHeight + EXPORT_CREDIT_PADDING + index * EXPORT_CREDIT_LINE_HEIGHT;
    // maxWidth squeezes rather than clips a single word wider than the canvas.
    ctx.fillText(line, EXPORT_CREDIT_PADDING, y, creditWidth);
  });
  ctx.restore();

  const blob = await toBlob(canvas);
  onProgress?.(100);
  downloadBlob(blob, exportFilename(genes));
}
