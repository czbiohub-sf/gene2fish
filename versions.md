# Changelog

## v1.4 — Lightbox keyboard navigation (2026-05-26)

**Branch:** `feature/v1.4-lightbox-nav`

**Feature: Step through images with ← / → from inside the lightbox**

Previously, comparing several images meant closing the lightbox, clicking the
next image, reading its metadata, closing, clicking the next, and so on. The
lightbox now supports leafing through images directly: pressing the Right
arrow advances to the next image, Left arrow goes back, with no need to
close the modal between images. Two on-screen buttons (`‹` / `›`) on the
overlay edges do the same thing, and are visibly greyed out (`disabled`) at
the first and last image so the boundary is discoverable. `Esc` and
click-outside still close the lightbox as before.

Navigation order matches the visual reading order of the grid: first through
the 1/3/6/10 images of the current cell, then to the next cell to the right,
wrapping to the leftmost cell of the next stage row down. The flat ordered
list is recomputed (via `useMemo`) whenever the grid contents change, so
filtering by stage range or anatomy automatically constrains navigation to
currently-visible images.

**Changed files:**
- `frontend/src/components/ExpressionGrid.jsx` — replaced single-image `lightboxImage` state with `lightboxIndex: number | null`; new `flatImages` `useMemo` walks `rows × genes × cell.slice(0, nImages)` to produce a row-major ordered list; `ImageCell` `onClick` resolves the clicked image to its index via `findIndex(x => x.image_id === img.image_id)`; passes `image`, `onPrev`, `onNext`, `hasPrev`, `hasNext`, `onClose` to `<Lightbox>`
- `frontend/src/components/Lightbox.jsx` — new props `onPrev`, `onNext`, `hasPrev`, `hasNext`; existing keydown `useEffect` extended with `ArrowLeft`/`ArrowRight` branches (guarded by the `hasPrev`/`hasNext` flags); two new `<button className="lightbox-nav ...">` elements rendered as siblings of `.lightbox-inner` inside the overlay (so they sit on the dark backdrop and are not clipped by `.lightbox-inner`'s `overflow-y: auto`); click handlers use a small `stopAndCall` wrapper to keep clicks from bubbling to the overlay's close handler
- `frontend/src/styles/main.css` — new `.lightbox-nav`, `.lightbox-nav-prev`, `.lightbox-nav-next` rules: 44px round buttons, vertically centred via `top: 50%; transform: translateY(-50%)`, positioned 24px from the overlay edges, semi-transparent white background with a soft shadow; `:disabled` state at `opacity: 0.3` and `cursor: not-allowed`

**Verified:**
- Within-cell navigation: with `nImages=6` on a multi-image gene, `→` steps through the cell's images in displayed order, then continues into the next cell to the right
- Cross-row navigation: at the right edge of a stage row, `→` jumps to the leftmost image of the next stage row down
- Boundary cue: at the first image the `‹` button is visibly greyed out and `disabled`, and `←` does nothing; same behavior for `›` and `→` at the last image
- `Esc` and click-outside still close the lightbox

---

## v1.3 — Anatomy-driven gene discovery & stage dropdown cleanup (2026-05-22)

**Branch:** `feature/v1.3-anatomy-discovery`

**Feature: Anatomy → suggested-genes strip**

Previously the anatomy search box did nothing visible until at least one gene
had been queried — `useGeneData` skips the API call when `genes.length === 0`,
so the term silently filtered nothing. Now, picking an anatomy term from the
autocomplete (e.g. `pronephros`) shows a horizontally-scrollable strip of gene
chips above the expression grid, listing every gene whose images include that
anatomy term, sorted by descending image count. Clicking a chip adds the gene
to the queried set; already-queried chips are dimmed and disabled. A
"Show Top 50 / Top 100 / All" selector controls strip length (All = server cap
of 1000). The strip also appears on direct URL load (`?anatomy=pronephros`),
so shareable links surface it without typing.

The new endpoint uses **exact** anatomy-name match (lowercased), distinct from
the **substring** filter used by the image-grid filter — intentional asymmetry:
the dropdown gives the user a verbatim term, and substring would surprisingly
conflate terms like `brain` with `hindbrain`/`midbrain` in the suggestion view.

**Changed files:**
- `backend/gene2image/data_loader.py` — accumulate `anatomy_counts: dict[str, dict[str, int]]` in the existing record loop; materialize `anatomy_index: dict[str, list[tuple[str, int]]]` pre-sorted desc by image count, tie-break by symbol; exposed on app state
- `backend/gene2image/models.py` — new `AnatomyGene` Pydantic model (`gene_symbol`, `image_count`)
- `backend/gene2image/routes.py` — new `GET /api/anatomy/{anatomy_name}/genes?limit=N` (default 50, max 1000); 404 on unknown term; comment noting the exact-vs-substring asymmetry
- `frontend/src/hooks/useAnatomyGenes.js` — new; mirrors `useGeneData` pattern (cancelled flag, loading/error state); `useEffect` deps `[anatomy, limit]`
- `frontend/src/components/AnatomySuggestedGenes.jsx` — new; renders header (title + limit `<select>`) and chip strip; local `limit` state resets to 50 when `anatomy` changes; returns `null` when no anatomy or zero suggestions
- `frontend/src/styles/main.css` — new `.suggested-genes-wrap` / `-header` / `-strip` / `-chip` / `.chip-count` styles; chips reuse the existing `.meta-tag` `#eff6ff` / `#1d4ed8` palette
- `frontend/src/App.jsx` — render `<AnatomySuggestedGenes>` between `<header>` and `<main>`, passing `anatomy`, `genes`, `addGene`

**Verified:** `curl /api/anatomy/pronephros/genes?limit=5` returns
`emilin1a (27), nherf1a (22), lama5 (20), enpp6 (18), glud1a (16)` — matches
the raw-JSON aggregation exactly. `limit=1000` returns 64 (the full set for
`pronephros`). 404 returned for unknown terms.

**Feature: Stage dropdown shows only populated stages, "1-cell" → "unspecified"**

The stage filter dropdown previously listed all 37 canonical zebrafish stages
even though the Thisse dataset only populates 13 of them, making 24 entries
non-functional. The dropdown now only shows stages that have at least one
image in the loaded dataset.

The `Zygote:1-cell` display label is renamed to `unspecified` because in
practice this stage carries default/placeholder annotations from the 2004
high-throughput Thisse screen (`ZDB-PUB-040907-1` contributes ~90% of
1-cell records, 4,441 of its 30,199 entries) rather than literal 1-cell-stage
in situ signal. The underlying stage_name (`Zygote:1-cell`) and begin_hours
(`0.00`) are unchanged, so it remains first in the dropdown.

**Changed files:**
- `backend/gene2image/stage_utils.py` — `Zygote:1-cell` display label changed from `"1-cell"` to `"unspecified"`
- `backend/gene2image/data_loader.py` — collect `populated_stage_hours: set[float]` during load; exposed on app state
- `backend/gene2image/routes.py` — `/api/stages` filters `CANONICAL_STAGES` to only those whose `begin_hours` are in `populated_stage_hours`; endpoint takes `Request` to read app state

**Verified:** `/api/stages` returns 13 entries instead of 37; first entry has
`display_label: "unspecified"` and `begin_hours: 0.0`; last entry is
`Larval:Day 5`.

**Feature: Total-count header on suggested-genes strip**

The strip header previously read e.g. `Genes with expression in brain (50)` —
where `50` was just the limit slice, not the actual number of genes in the
dataset annotated with that term. Misleading. Now: `(187, showing 50)` where
`187` is the true total and `showing N` reflects the limit selector. When
`Show: All` is picked and everything fits, the `showing N` suffix is omitted.

**Changed files:**
- `backend/gene2image/models.py` — new `AnatomyGenesResponse` Pydantic model wrapping `{total: int, genes: list[AnatomyGene]}`
- `backend/gene2image/routes.py` — `GET /api/anatomy/{anatomy_name}/genes` now returns the wrapper instead of a bare list; `total = len(pairs)`, `genes = pairs[:limit]`
- `frontend/src/hooks/useAnatomyGenes.js` — return shape now `{suggestions, total, loading, error}`; both reset together when anatomy clears
- `frontend/src/components/AnatomySuggestedGenes.jsx` — header renders `({total}, showing {suggestions.length})` with the "showing N" suffix only when `total > suggestions.length`
- `frontend/src/styles/main.css` — new `.suggested-genes-subcount` for the muted "showing N" text

**Feature: Marker-discovery anatomy filter (per-gene semantics)**

Previously the anatomy filter was per-image: if only one of a gene's images
carried the term `pronephric mesoderm`, the grid collapsed to that single
image. That defeats marker discovery — the user wants to see whether the
gene also lights up at other developmental stages. Now the filter is a
per-gene gate: if **any** image of the gene carries the anatomy term, ALL
of the gene's images pass through (the stage range still trims by hour).

**Changed files:**
- `backend/gene2image/routes.py` — `_filter_records` refactored: anatomy is now a per-gene gate (early-return `[]` if no record matches), followed by per-image stage-range filtering. New helper `_record_matches_anatomy`. Caller contract (already satisfied by both endpoints) is that `records` is a per-gene list pulled from `gene_index`.

**Verified:** `POST /api/genes/batch` with `{"genes":["emilin1a"],"anatomy":"pronephric mesoderm","n_images":10}` now returns images at 5 stages (1-4 somites, 14-19 somites, 20-25 somites, Prim-15, High-pec) — identical to the no-filter response. With `anatomy:"notarealterm"` the gene returns 0 records (gate still works).

**Fix: Chip strip scrollbar no longer overlaps gene names**

The horizontal scrollbar sat directly under the chips, making gene symbols
hard to read while scrolling. Bottom padding on `.suggested-genes-strip`
increased from 2px to 14px ([`frontend/src/styles/main.css`](frontend/src/styles/main.css)).

---

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
