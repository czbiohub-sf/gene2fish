# gene2image

Zebrafish gene expression image browser. Browse Thisse in situ hybridization images from ZFIN by gene symbol and developmental stage.

Images are hotlinked directly from ZFIN (zfin.org) under CC BY 4.0. Never downloaded or proxied.

## Data

The app requires a pre-built JSON index of Thisse images. This file is **not** included in the repository — you must build it yourself by running the extractor (see below).

Expected location:
```
/path/to/gene2image_data/image_metadata.json
```

The backend looks for `image_metadata_v2.json` first and falls back to `image_metadata.json`. Set the `GENE2IMAGE_DATA_DIR` environment variable to the directory containing the file.

## Building the data file

`zfin_image_metadata_extractor.py` downloads the 13 required TSVs from ZFIN, joins them, and writes `image_metadata.json` + `image_metadata.tsv`. Pick a directory where the data should live (e.g. `~/projects/gene2image_data`) and run the extractor from there:

```bash
mkdir -p /path/to/gene2image_data
cd /path/to/gene2image_data
uv run python /path/to/gene2image/zfin_image_metadata_extractor.py
```

By default the extractor:
- Downloads the 13 ZFIN TSV files into `./zfin_data/` (skipped if already present)
- Filters to the 5 Thisse publications (`ZDB-PUB-040907-1`, `ZDB-PUB-010810-1`, `ZDB-PUB-051025-1`, `ZDB-PUB-080227-22`, `ZDB-PUB-080220-1`)
- Writes `image_metadata.json` and `image_metadata.tsv` to the current working directory

Useful flags:
- `--all-images` — process every ZFIN image, not just the Thisse subset
- `--image-ids ZDB-IMAGE-…,ZDB-IMAGE-…` — process specific image IDs only
- `--pub-ids ZDB-PUB-…,ZDB-PUB-…` — filter by a different publication set
- `--output-prefix image_metadata_v2` — change output filename (use this to write the `_v2` file the backend prefers)
- `--input-dir /some/path` — keep the downloaded TSVs somewhere other than `./zfin_data`
- `--no-download` — fail instead of downloading missing TSVs

The extractor processes ~180k images/sec and finishes in under a second once the TSVs are present.

After building, set the env var to the directory holding the JSON:

```bash
export GENE2IMAGE_DATA_DIR=/path/to/gene2image_data
```

## Setup

### Backend

```bash
cd /path/to/gene2image
uv sync
GENE2IMAGE_DATA_DIR=/path/to/gene2image_data \
  uvicorn gene2image.main:app --reload --port 8000 --app-dir backend
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
# API calls are proxied to http://localhost:8000
```

### Docker

The Docker image builds the Vite frontend, bakes the Thisse image index into the
image at build time (the build runs `zfin_image_metadata_extractor.py`, which
downloads the ZFIN TSVs — so the build needs network access to zfin.org), and
serves the SPA from the FastAPI app on the same port as the API.

```bash
docker build -t gene2image .
docker run --rm -p 8000:8000 gene2image
```

The image is self-contained: `GENE2IMAGE_DATA_DIR` defaults to `/data` inside the
image, where the prebuilt `image_metadata.json` lives — no data volume needs to be
mounted. Refresh the baked data by rebuilding. To serve a different dataset, mount
it and override the env var:

```bash
docker run --rm -p 8000:8000 \
  -e GENE2IMAGE_DATA_DIR=/data \
  -v /path/to/gene2image_data:/data:ro \
  gene2image
```

The container runs as a non-root user (UID 10001). Open `http://localhost:8000`.
The container exposes `/api/health` for deployment health checks.

## Usage

1. Type a gene symbol (e.g. `pacsin2`, `tbxta`, `pax2a`) in the search box and press Enter
2. The expression grid shows images for each developmental stage where expression data exists
3. Hover an image for a quick summary; click for full metadata
4. Use the stage range slider to narrow the timepoint view
5. Use the anatomy gene search to find additional genes expressed in a specific structure; selected genes are added as new columns without filtering images already open in the grid

## Rate limiting

gene2image loads images directly from ZFIN's image server (hotlinking). To avoid
triggering ZFIN's per-IP rate limit, images are loaded sequentially with a 150 ms
delay between requests rather than all at once. A grid with 30 images will fully
load in approximately 4–5 seconds — the grid fills in progressively as each image
arrives.

If you do hit a rate limit (images stop loading or show as broken), wait a few
minutes before searching for new genes. Searching for a new gene automatically
cancels any pending loads from the previous search.

## Attribution

Images from ZFIN (zfin.org). Thisse et al. in situ hybridization data.
Licensed under CC BY 4.0. Attribution: Thisse, B., Thisse, C. et al.
