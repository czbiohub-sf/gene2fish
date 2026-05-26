# Changelog

## v1.2 — Sequential image load queue & full attribution footer (2026-04-27)

**Branch:** `feature/v1.2-image-queue`

**Feature: Full references & creator credits in footer**
- Footer now lists all 5 Thisse dataset publications with proper author/year/title citations,
  each linking to their ZFIN publication page (ZDB-PUB-010810-1 through ZDB-PUB-080227-22)
- Added creator credit line: Vera Janssen & Leandro Lima
- Footer restructured into three sections: license line, references list, creators

**Changed files (footer):**
- `frontend/src/components/Attribution.jsx` — full rewrite with `THISSE_PUBLICATIONS` list and three-section footer
- `frontend/src/styles/main.css` — new footer section styles (`.footer-references`, `.footer-ref-list`, `.footer-creators`)

**Problem:** Loading a gene with many stages fired 50–200 simultaneous HTTP
requests to ZFIN's image server, triggering their per-IP rate limiter and
blocking access for several hours.

**Fix:** Introduced a module-level image load queue (`useImageQueue` hook).
`SingleImage` components start with no `src` and register with the queue on
mount. The queue releases one image request every 150 ms (~6/sec), filling
the grid progressively without triggering ZFIN's rate limit. Searching for a
new gene flushes pending loads from the previous search via `resetQueue()`.
`loading="lazy"` removed from `<img>` tags — timing is now controlled
entirely by the queue.

**Changed files:**
- `frontend/src/hooks/useImageQueue.js` — new; module-level queue singleton + `useImageQueue` hook + `resetQueue` export
- `frontend/src/components/ImageCell.jsx` — `SingleImage` uses queue; removed `loading="lazy"`
- `frontend/src/hooks/useGeneData.js` — calls `resetQueue()` at the start of each new fetch
- `README.md` — added Rate limiting section
- `versions.md` — this entry

---

## v1.1 — Attribution & column width fix (2026-04-21)

**Branch:** `feature/v1.1-attribution-column-fix`

**Feature: Proper attribution & reference links**
- Attribution footer now links to the canonical Thisse dataset entry on ZFIN (`ZDB-PUB-010810-1`) instead of attributing with plain text only
- Lightbox: `publication_id` is now a clickable link to `https://zfin.org/{publication_id}`
- Lightbox: `pubmed_id` (when present) is now a clickable link to `https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/`

**Fix: Column width in multi-image mode**
- Previously, all columns used `--n: {nImages}` for their CSS width regardless of how many images actually existed for that gene, making columns unnecessarily wide
- `ExpressionGrid` now computes `colMaxImages[symbol]` — the maximum number of images present in any stage cell for that gene, capped at `nImages`
- Column headers (`<th>`) and empty cells get an inline width matching `colMaxImages`, so columns are only as wide as their actual content
- `ImageCell` now accepts a `colMax` prop and uses it for the `--n` CSS variable, keeping the `<td>` width consistent with its column header

**Changed files:**
- `frontend/src/components/Attribution.jsx` — added ZFIN reference link
- `frontend/src/components/Lightbox.jsx` — publication_id and pubmed_id rendered as links
- `frontend/src/styles/main.css` — added `.meta-value a` link styles; export-related styles removed (feature deferred)
- `frontend/src/components/ExpressionGrid.jsx` — added `colMaxImages` useMemo; `<th>` and empty `<td>` get inline width; `ImageCell` receives `colMax` prop
- `frontend/src/components/ImageCell.jsx` — added `colMax` prop; `--n` set to `effectiveColMax` instead of global `n`

---

## v0.4 — Multi-image view (2026-04-14)

**Branch:** `feature/multi-image-view` (not yet merged to main)

**Feature:** Users can now view 1, 3, 6, or 10 images per gene × timepoint cell using a toggle in the header ("Images per cell"). Default is 1 (unchanged from v0.3). Images are ranked by preparation type (whole-mount first) then anatomy term count.

**Changed files:**
- `backend/gene2image/models.py` — Added `n_images: int = 1` to `BatchRequest`
- `backend/gene2image/stage_utils.py` — Extracted `_score_image()`, added `select_top_n(images, n)` returning up to n ranked images per stage
- `backend/gene2image/routes.py` — `_select_representatives` now takes `n` and uses `select_top_n`; batch endpoint passes `body.n_images`
- `frontend/src/hooks/useUrlState.js` — `nImages` (1/3/6/10) added to URL state, synced as `?n_images=N`
- `frontend/src/hooks/useGeneData.js` — Passes `n_images` in batch request, re-fetches on change
- `frontend/src/App.jsx` — "Images per cell" toggle control with buttons 1 / 3 / 6 / 10
- `frontend/src/components/ExpressionGrid.jsx` — Lookup now stores `ImageRecord[]` per stage cell
- `frontend/src/components/ImageCell.jsx` — Renders N images side-by-side; each clickable for lightbox; failed images disappear silently in multi mode
- `frontend/src/styles/main.css` — Toggle button styles; multi-image flexbox cell layout

**Image ordering fix:** Within a stage cell, images are now sorted by descending image ID (highest number first) as the final tiebreaker after whole-mount and anatomy count. ZFIN image IDs are assigned sequentially, and later images tend to show more varied orientations (e.g. lateral views come after dorsal), so showing higher IDs first increases orientation diversity when displaying 3/6/10 images per cell.

**Known issue — ZFIN image loading:** ZFIN appears to enforce per-IP rate limits on their image server. After a burst of image requests (loading a gene with many timepoints, or switching to 6/10 images per cell), the IP gets temporarily blocked and subsequent images fail to load. Images already cached in the browser are unaffected. The workaround is to wait a few minutes before loading more genes. A future fix could add request throttling on the frontend to stay under the rate limit.

---

## v0.3 — Extractor performance fix (2026-04-14)

**Changed:** `zfin_image_metadata_extractor.py`

The extractor was silently producing empty output files when run on the full 53k-image dataset because every per-image lookup was a full pandas DataFrame scan (`df[df[col] == val]`), repeated 53,595 times — O(n²) overall. The process would time out or be killed before writing any output.

**Fix:** Added `_build_indexes()` to `ZFINImageMetadataExtractor`, called once after data load. Converts all 13 DataFrames into Python dicts for O(1) access. Processing time went from hours (did not complete) to under 1 second (~180k images/sec).

No changes to the backend or frontend.

---

## v0.2 — Per-image stage data fix (2026-04-14)

**Changed:** `zfin_image_metadata_extractor.py`, `image_metadata.json` regenerated

**Root cause of the bug:** Every image for a gene showed up in only one stage row (always the earliest stage in the experiment, e.g. 50%-epiboly), even when images clearly belonged to later stages like 14-19 somites.

**Why it happened:** The `developmental_stages` array in the JSON is not per-image — it is a study-level annotation listing all stages observed across the entire expression experiment. All images from one experiment shared identical stage metadata. The original extractor joined `xpat_stage_anatomy` on `expression_id` (whole-experiment), which collapsed every image in an experiment into the same stage list.

**Fix:** Changed the join to use `expression_result_id` (figure-specific). Each figure in ZFIN links to a set of expression result IDs via `xpatfig_fish`, and each result ID in `xpat_stage_anatomy` carries its own start/end stage and anatomy. This gives each image its own correct stage assignment.

**Verified:** `pacsin2` image `ZDB-IMAGE-060216-703` now correctly appears at 14-19 somites (matching ZFIN website). `pax2a` now returns 6 distinct images at 6 different stages instead of 47 images all at 50%-epiboly.

**Data file:** `image_metadata.json` regenerated — 115 MB (down from 253 MB; smaller because per-image stage/anatomy is now specific rather than the full experiment-level union).

No changes to the backend or frontend.

---

## v0.1 — Initial build (2026-04-13)

First working version of the full app stack.

**Backend** (`backend/gene2image/`):
- `main.py` — FastAPI app with lifespan data loader, CORS middleware
- `data_loader.py` — loads `image_metadata.json`, strips literal `NaN` values (pandas export artifact), parses `begin_hours`/`end_hours` strings to float, builds in-memory gene and anatomy indexes
- `stage_utils.py` — hardcoded canonical 37-stage list (Zygote → Adult), `assign_canonical_stage()`, `select_representative()` (whole-mount preferred, then most anatomy terms)
- `models.py` — Pydantic response models for all API endpoints
- `routes.py` — 5 endpoints: gene autocomplete, single-gene images, batch images, anatomy autocomplete, canonical stage list. Image URL construction (`_annot.jpg` primary, `.jpg` fallback). Representative image selection done server-side.

**Frontend** (`frontend/src/`):
- Gene × timepoint grid: genes as columns, canonical stages as rows, empty rows collapsed
- `GeneInput` — autocomplete with keyboard navigation, 300ms debounce
- `StageFilter` — dual-select stage range filter
- `AnatomyFilter` — autocomplete anatomy filter, 300ms debounce
- `ImageCell` — lazy loading, `_annot.jpg` → `.jpg` → placeholder 404 fallback chain, hover tooltip, click to lightbox
- `Lightbox` — full metadata modal (gene, stage, anatomy, probe/EST, fish line, human orthologs, disease associations, UniProt), link to ZFIN, closes on Esc or click-outside
- `useUrlState` — genes + filters synced to URL params for shareable links
- `useGeneData` — batch fetch via `POST /api/genes/batch`
- JetBrains Mono font via `@fontsource/jetbrains-mono`
- CC BY 4.0 attribution footer

**Project scaffolding:**
- `pyproject.toml` with `uv` for Python dependency management
- `.gitignore` excluding `gene2image_data/` (data files never committed)
- `README.md` with setup instructions
- `check_frontend.sh` / `test_system.sh` smoke test scripts
