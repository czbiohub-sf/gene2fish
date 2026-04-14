# Claude Code Prompt: gene2image — Zebrafish Gene Expression Browser

## Project Overview

Build a web application that lets researchers browse zebrafish in situ hybridization images from the Thisse dataset (hosted on ZFIN). Images are displayed via hotlinking — `<img>` tags pointing directly to ZFIN's servers. ZFIN has explicitly authorized this use under CC BY 4.0, and prefers hotlinking over bulk download (it helps their grant usage statistics).

## Paths

- **Data (read-only, do not modify):** `/Users/vera.janssen/projects/gene2image_data/`
  - Contains `zfin_thisse_index.json` — the pre-built index of all Thisse images with metadata
- **Application code (this repo):** `/Users/vera.janssen/softwares/gene2image/`

## Repository Structure

Follow the same layout as JoOkuma's project (backend/, frontend/, docs/, examples/, scripts/, tests/ at root level, with pyproject.toml and uv for Python packaging):

```
gene2image/
├── backend/           # Python FastAPI backend (serves the JSON index as API)
│   └── gene2image/    # Python package
│       ├── __init__.py
│       ├── main.py        # FastAPI app, CORS, lifespan
│       ├── data_loader.py # Load JSON, build indexes, handle NaN
│       ├── models.py      # Pydantic response models
│       ├── routes.py      # API endpoint definitions
│       └── stage_utils.py # Canonical stage ordering, hour-based sorting
├── frontend/          # Vite + React frontend
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── GeneInput.jsx       # Search bar with autocomplete
│       │   ├── ExpressionGrid.jsx  # Gene × timepoint grid
│       │   ├── ImageCell.jsx       # Single cell: lazy img, tooltip, click
│       │   ├── StageFilter.jsx     # Timepoint range filter
│       │   ├── AnatomyFilter.jsx   # Anatomy term filter
│       │   ├── Lightbox.jsx        # Full-size modal with all metadata
│       │   └── Attribution.jsx     # CC BY 4.0 footer
│       ├── hooks/
│       │   ├── useGeneData.js      # Fetch gene images from backend
│       │   └── useUrlState.js      # Sync genes + filters with URL params
│       ├── utils/
│       │   └── stageMapping.js     # Canonical stage list, display labels
│       └── styles/
│           └── main.css
├── docs/              # PRD, architecture notes
├── examples/          # Example queries, demo screenshots
├── scripts/           # Utility scripts (data processing, deployment)
├── tests/             # Backend + frontend tests
├── .gitignore
├── .python-version
├── pyproject.toml     # Python project config (backend deps: fastapi, uvicorn)
├── README.md
├── check_frontend.sh
├── test_system.sh
└── uv.lock
```

## Data Schema (Actual JSON Structure)

The JSON file is an **array of image records**. Each record represents one image. Here is the exact schema per record:

```json
{
  "image_id": "ZDB-IMAGE-011001-1",
  "image_info": {
    "image_id": "ZDB-IMAGE-011001-1",
    "figure_id": "ZDB-FIG-050630-11537",
    "image_preparation": "whole-mount"
  },
  "expression": {
    "expression_id": "ZDB-XPAT-011001-1",
    "expression_type": "mRNA in situ hybridization",
    "expression_type_mmo_id": "MMO:0000658",
    "est_id": "ZDB-EST-010914-39",
    "est_symbol": "cb47",
    "probe_quality": "4"
  },
  "gene": {
    "gene_id": "ZDB-GENE-011115-1",
    "gene_symbol": "ywhag1",
    "so_id": "SO:0001217",
    "ncbi_gene_id": "117604"
  },
  "fish": {
    "fish_id": "ZDB-FISH-150901-29084",
    "fish_name": "AB/TU",
    "fish_abbreviation": "AB/TU",
    "genotype_id": "ZDB-GENO-010924-10"
  },
  "environment": {
    "environment_id": "ZDB-EXP-041102-1",
    "zeco_term_name": "standard conditions",
    "zeco_term_id": "ZECO:0000103",
    "chebi_term_name": NaN,
    "chebi_term_id": NaN
  },
  "publication": {
    "publication_id": "ZDB-PUB-010810-1",
    "pubmed_id": NaN
  },
  "anatomical_locations": [
    {
      "anatomy_id": "ZFA:0000029",
      "anatomy_name": "hindbrain",
      "expression_found": "t"
    }
  ],
  "developmental_stages": [
    {
      "stage_id": "ZDB-STAGE-010723-30",
      "stage_obo_id": "ZFS:0000026",
      "stage_name": "Segmentation:14-19 somites",
      "begin_hours": "16.00",
      "end_hours": "19.00"
    }
  ],
  "human_orthologs": [
    {
      "human_symbol": "YWHAG",
      "human_name": "tyrosine 3-monooxygenase/...",
      "omim_id": "605356",
      "hgnc_id": "12852",
      "entrez_gene_id": "7532"
    }
  ],
  "disease_associations": [
    {
      "do_term_name": "developmental and epileptic encephalopathy 56",
      "do_term_id": "DOID:0080282",
      "omim_term_name": "...",
      "omim_id": "617665",
      "human_ortholog_symbol": "YWHAG"
    }
  ],
  "uniprot_ids": ["Q6PC29"]
}
```

**Critical notes on the data:**
- Each record is ONE image. Multiple records share the same `gene.gene_symbol`.
- An image can have MULTIPLE `developmental_stages` entries (= a range of stages).
- An image can have MULTIPLE `anatomical_locations`.
- `NaN` appears as literal unquoted `NaN` in the JSON (from pandas export). You MUST handle this — replace `NaN` with `null` before JSON parsing (e.g. regex `re.sub(r'\bNaN\b', 'null', raw_text)`).
- `begin_hours` and `end_hours` are strings like `"16.00"` — parse to float.

## Image URL Construction

```
https://zfin.org/imageLoadUp/{pub_year}/{pub_id}/{image_id}_annot.jpg
```

Derive `pub_year` from `publication.publication_id`:
- `ZDB-PUB-010810-1` → extract `"01"` → year `"2001"`
- `ZDB-PUB-040907-1` → extract `"04"` → year `"2004"`
- Logic: `pub_id.split("-")[2][:2]` → prepend `"20"`

Prefer `_annot.jpg`. If it 404s, fall back to `.jpg` without `_annot`.

## Application Specification

### Core Layout: Gene × Timepoint Grid

The main view is a **grid**:
- **Columns** (left to right) = genes, in the order the user entered them
- **Rows** (top to bottom) = developmental timepoints, in chronological order by `begin_hours`
- Each **cell** = the representative image for that gene at that timepoint, or empty if none

### Canonical Stage Ordering (use begin_hours for sort)

```
Stage Name                    begin_hours   Display Label
─────────────────────────────────────────────────────────
Zygote:1-cell                 0.00          1-cell
Cleavage:2-cell               0.75          2-cell
Cleavage:4-cell               1.00          4-cell
Cleavage:8-cell               1.25          8-cell
Cleavage:16-cell              1.50          16-cell
Cleavage:32-cell              1.75          32-cell
Cleavage:64-cell              2.00          64-cell
Cleavage:128-cell             2.25          128-cell
Blastula:256-cell             2.50          256-cell
Blastula:512-cell             2.75          512-cell
Blastula:1k-cell              3.00          1k-cell
Blastula:High                 3.33          High
Blastula:Oblong               3.67          Oblong
Blastula:Sphere               4.00          Sphere
Blastula:Dome                 4.33          Dome
Gastrula:30%-epiboly          4.67          30%-epiboly
Gastrula:50%-epiboly          5.25          50%-epiboly
Gastrula:Germ-ring            5.67          Germ-ring
Gastrula:Shield               6.00          Shield
Gastrula:75%-epiboly          8.00          75%-epiboly
Gastrula:90%-epiboly          9.00          90%-epiboly
Gastrula:Bud                  10.00         Bud
Segmentation:1-4 somites      10.33         1-4 somites
Segmentation:5-9 somites      11.67         5-9 somites
Segmentation:10-13 somites    14.00         10-13 somites
Segmentation:14-19 somites    16.00         14-19 somites
Segmentation:20-25 somites    19.00         20-25 somites
Pharyngula:Prim-5             24.00         Prim-5 (24 hpf)
Pharyngula:Prim-15            30.00         Prim-15 (30 hpf)
Pharyngula:Prim-25            36.00         Prim-25 (36 hpf)
Pharyngula:High-pec           42.00         High-pec (42 hpf)
Hatching:Long-pec             48.00         Long-pec (48 hpf)
Hatching:Pec-fin              60.00         Pec-fin (60 hpf)
Larval:Protruding-mouth       72.00         Protruding-mouth (72 hpf)
Larval:Day 4                  96.00         Day 4 (96 hpf)
Larval:Day 5                  120.00        Day 5 (120 hpf)
Adult                         2160.00       Adult
```

### Stage-to-Row Mapping

Each image has a `developmental_stages` array. To assign to a row:
1. Take the **minimum** `begin_hours` (parsed as float) across all stages in the array
2. Map to the nearest canonical stage row (closest `begin_hours`)
3. Only show rows that have at least one image across the queried genes (collapse empty rows)

### Representative Image Selection

When multiple images for the same gene map to the same canonical timepoint:
1. Prefer `image_info.image_preparation == "whole-mount"`
2. Prefer images with more anatomy terms (richer annotation)
3. Otherwise pick first encountered

Show **1 image per gene per canonical timepoint** by default.

### User Input

- Text input at the top: gene symbols, comma-separated or one per line
- Enter or "Add" button to add genes as columns
- Gene columns appear left to right in input order
- Each column header: gene symbol in monospace + × remove button
- **Autocomplete**: debounced (300ms), searches all unique `gene.gene_symbol` values

### Stage / Timepoint Filtering

- Multi-select or dual-handle range slider over the canonical stage list
- When user selects e.g. "14-19 somites" through "Prim-5", only rows within that `begin_hours` range are shown
- Images whose stage range overlaps with the filter are included

### Anatomy Filter

- Text input with autocomplete over all unique `anatomy_name` values in the dataset
- When active, only show images with at least one matching anatomy term

### Image Behavior

- `<img src="{url}" loading="lazy">` — hotlink only, never download/proxy
- **Hover tooltip**: stage name + hpf, anatomy terms (comma-joined), image ID, publication
- **Click → lightbox modal**: full-res image, all metadata (gene, stages, anatomy, probe/EST, fish line, human orthologs, disease associations, uniprot IDs), link to `https://zfin.org/{image_id}`
- **404 handling**: placeholder box with image ID text and clickable link to ZFIN

### Attribution Footer

```
Images from ZFIN (zfin.org). Thisse et al. in situ hybridization data.
Licensed under CC BY 4.0. Attribution: Thisse, B., Thisse, C. et al.
```

## Backend (FastAPI, `backend/gene2image/`)

### Startup
- Load JSON from `$GENE2IMAGE_DATA_DIR/zfin_thisse_index.json`
- Replace `NaN` → `null` before parsing
- Parse `begin_hours`/`end_hours` to float
- Build in-memory indexes:
  - `gene_index: dict[str, list[ImageRecord]]` — gene_symbol → images
  - `anatomy_index: dict[str, set[str]]` — anatomy_name → set of gene_symbols
  - `gene_list: list[str]` — sorted unique gene symbols (for autocomplete)
  - `anatomy_list: list[str]` — sorted unique anatomy terms

### Endpoints

```
GET  /api/genes/search?q={partial}
     → returns list of matching gene symbols (case-insensitive prefix match)

GET  /api/genes/{symbol}/images?stage_min={float}&stage_max={float}&anatomy={term}
     → images for one gene, optionally filtered
     → sorted by earliest begin_hours
     → includes constructed image_url per record

POST /api/genes/batch
     body: {"genes": ["shha", "fgf8a", "pax2a"], "stage_min": null, "stage_max": null, "anatomy": null}
     → images for multiple genes, grouped by gene_symbol

GET  /api/anatomy/search?q={partial}
     → autocomplete for anatomy terms

GET  /api/stages
     → returns canonical stage list with begin_hours, for the filter UI
```

Include CORS middleware (allow_origins=["*"] for dev).

## Frontend (React + Vite, `frontend/`)

### Design
- Clean, minimal, scientific tool aesthetic
- White background, subtle gray borders (#e5e7eb)
- Monospace font for gene names and IDs (`font-family: 'JetBrains Mono', 'Fira Code', monospace`)
- Sans-serif for labels (`system-ui, -apple-system, sans-serif`)
- Column headers: gene symbol bold monospace, small × button
- Row headers: display label + hpf in parentheses (e.g. "Prim-5 (24 hpf)")
- Empty cells: light gray (#f9fafb) with dashed border
- Image cells: fixed size ~180×180px, `object-fit: contain`, subtle shadow on hover

### Performance
- Fetch gene list once on mount for autocomplete
- Fetch image data per gene via the batch endpoint when the user submits
- Lazy load images with `loading="lazy"` on `<img>` tags
- Debounce autocomplete (300ms)
- Only render rows that have at least one image

### Additional Features
- **URL state**: `?genes=shha,fgf8a&stage_min=16&stage_max=48` — sync with URL so views are shareable
- **Export**: button that copies current grid as HTML table to clipboard
- **Column reorder**: drag-and-drop

## Rules

- Exclude any gene where `gene.gene_symbol` starts with "WITHDRAWN"
- All `<img>` src must point to `zfin.org` — never download, cache, or proxy
- Handle ZFIN server errors gracefully (placeholder, never crash the app)
- The JSON data file must NOT be committed to the git repo — document the expected path in README
- Add `**/gene2image_data/` to `.gitignore`

## Getting Started (put this in README.md)

```bash
# Clone and enter repo
cd /Users/vera.janssen/softwares/gene2image

# Backend
cd backend
uv sync
GENE2IMAGE_DATA_DIR=/Users/vera.janssen/projects/gene2image_data \
  uvicorn gene2image.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173, proxies API calls to :8000
```

Configure the Vite dev server to proxy `/api` to `http://localhost:8000`.
