# gene2fish

Zebrafish gene expression image browser. Browse Thisse in situ hybridization images from ZFIN by gene symbol and developmental stage.

Images originate from ZFIN (zfin.org) under CC BY 4.0. To stay resilient to
temporary ZFIN outages, images are served through the backend `/api/image-proxy`
endpoint, which reads them from our own S3 mirror and falls back to fetching live
from ZFIN when an object isn't mirrored. See [Image mirror](#image-mirror).

## Data

> **Using Docker?** You can skip this section. The Docker image bakes the
> Thisse image index into `/data` at build time, so `docker build && docker run`
> works with no extra data setup (see [Docker](#docker)). The steps below are for
> **local development**, where you build the JSON index yourself.

For local development the app requires a pre-built JSON index of Thisse images. This file is **not** included in the repository — you must build it yourself by running the extractor (see below).

Expected location:
```
/path/to/gene2image_data/image_metadata.json
```

The backend looks for `image_metadata_v2.json` first and falls back to `image_metadata.json`. Set the `GENE2IMAGE_DATA_DIR` environment variable to the directory containing the file.

## Building the data file (local dev)

`zfin_image_metadata_extractor.py` downloads the 14 required TSVs from ZFIN, joins them, and writes `image_metadata.json` + `image_metadata.tsv` + `gene_aliases.json`. Pick a directory where the data should live (e.g. `~/projects/gene2image_data`) and run the extractor from there:

```bash
mkdir -p /path/to/gene2image_data
cd /path/to/gene2image_data
uv run python /path/to/gene2image/zfin_image_metadata_extractor.py
```

By default the extractor:
- Downloads the 14 ZFIN TSV files into `./zfin_data/` (skipped if already present)
- Filters to the 5 Thisse publications (`ZDB-PUB-040907-1`, `ZDB-PUB-010810-1`, `ZDB-PUB-051025-1`, `ZDB-PUB-080227-22`, `ZDB-PUB-080220-1`)
- Writes `image_metadata.json` and `image_metadata.tsv` to the current working directory
- Writes `gene_aliases.json` (next to the JSON index): each in-dataset gene's stable ZFIN ID mapped to its previous/alias names (from ZFIN's `aliases.txt`), so the backend can resolve searches by older names (e.g. `oct4` → `pou5f3`). The backend loads it automatically when present; absent, gene search degrades to current symbols only.

Useful flags:
- `--all-images` — process every ZFIN image, not just the Thisse subset
- `--image-ids ZDB-IMAGE-…,ZDB-IMAGE-…` — process specific image IDs only
- `--pub-ids ZDB-PUB-…,ZDB-PUB-…` — filter by a different publication set
- `--output-prefix image_metadata_v2` — change output filename (use this to write the `_v2` file the backend prefers)
- `--input-dir /some/path` — keep the downloaded TSVs somewhere other than `./zfin_data`
- `--no-download` — fail instead of downloading missing TSVs
- `--min-records N` — exit non-zero if fewer than `N` records are extracted (default `0`, no check). The Docker build uses this to fail the build rather than bake an empty/partial index from a truncated download or drifted ZFIN file format.

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

The build runs the extractor with `--min-records 10000`, so a truncated download
or a drifted ZFIN file format fails the build instead of silently baking an empty
or partial index (the Thisse set is ~53k records).

```bash
docker build -t gene2fish .
docker run --rm -p 8000:8000 gene2fish
```

The image is self-contained: `GENE2IMAGE_DATA_DIR` defaults to `/data` inside the
image, where the prebuilt `image_metadata.json` lives — no data volume needs to be
mounted. Refresh the baked data by rebuilding. To serve a different dataset, mount
it and override the env var:

```bash
docker run --rm -p 8000:8000 \
  -e GENE2IMAGE_DATA_DIR=/mydata \
  -v /path/to/gene2image_data:/mydata:ro \
  gene2fish
```

The container runs as a non-root user (UID 10001). Open `http://localhost:8000`.
The container exposes `/api/health` for deployment health checks.

## Image mirror

To keep images loading when ZFIN is temporarily unavailable, the in-situ images
are mirrored into our own S3 bucket and served through the backend
`/api/image-proxy` endpoint. The proxy reads each image from S3 first and only
falls back to fetching live from ZFIN when the object isn't mirrored (or S3 is
unreachable), so a ZFIN outage no longer breaks image loading.

**Opt-in / no-op by default.** The proxy reads S3 only when
`GENE2IMAGE_IMAGE_S3_BUCKET` is set. When it's unset (e.g. local dev), the proxy
behaves exactly as before — a pure ZFIN passthrough — so no AWS setup is needed
to run the app locally.

Backend env vars (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `GENE2IMAGE_IMAGE_S3_BUCKET` | _(unset → S3 disabled)_ | Bucket holding the mirror |
| `GENE2IMAGE_IMAGE_S3_PREFIX` | `gene2fish/zfin-images` | Key prefix within the bucket |
| `GENE2IMAGE_IMAGE_S3_REGION` | `us-west-2` | Bucket region |

The deployment must grant the backend `s3:GetObject` on the bucket/prefix
(via an IAM role / service account; standard AWS credential chain). The bucket
stays **private** — images are never exposed publicly; they are streamed through
the backend.

### Populating the mirror

`zfin_image_mirror.py` reads `image_metadata*.json`, downloads each image from
ZFIN (the plain `.jpg`, plus the annotated `_annot.jpg` where it exists), and
uploads them to S3, mirroring the ZFIN path 1:1 so the backend can map a ZFIN URL
to a key by a prefix swap:

```
https://zfin.org/imageLoadUp/{year}/{pub}/{file}
  → s3://{bucket}/{prefix}/imageLoadUp/{year}/{pub}/{file}
```

The run is resumable (objects already present are skipped):

```bash
export GENE2IMAGE_DATA_DIR=/path/to/gene2image_data   # holds image_metadata*.json
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-west-2
python zfin_image_mirror.py                            # mirror everything
python zfin_image_mirror.py --limit 50 --dry-run       # smoke test, no uploads
```

Useful flags: `--workers N` (concurrency), `--overwrite` (re-upload existing),
`--skip-annot` (plain `.jpg` only), `--bucket` / `--prefix` / `--region`.

## Usage

1. Type a gene symbol (e.g. `pacsin2`, `tbxta`, `pax2a`) in the search box and press Enter
2. The expression grid shows images for each developmental stage where expression data exists
3. Hover an image for a quick summary; click for full metadata
4. Use the stage range slider to narrow the timepoint view
5. Use the anatomy gene search to find additional genes expressed in a specific structure; selected genes are added as new columns without filtering images already open in the grid

## Per-image analytics

Gene2Fish records an `Image View` custom event in Plausible when a visitor
intentionally opens a full-size image or navigates to the previous/next image in
the lightbox. Automatically loaded grid thumbnails, image retries, preloads, and
PNG exports are not counted.

Each event contains these custom properties:

| Property | Description |
| --- | --- |
| `image_id` | Stable ZFIN image identifier and primary reporting dimension |
| `gene_symbol` | Gene associated with the image |
| `stage` | Display label for the developmental stage |
| `publication_id` | ZFIN publication identifier, when available |

The Plausible site for `gene2fish.apps.czbiohub.org` must have an unrestricted
custom event goal named exactly `Image View` and the four properties above
enabled under **Settings → Custom properties**. Do not add fixed property values
to the goal: values such as the image ID and gene symbol are supplied dynamically
by each event.

To report image usage, select the desired date range in Plausible, choose the
`Image View` goal, open **Properties**, and select `image_id`. **Total** (or
**Events** in the Stats API) is the number of intentional image opens;
**Uniques** (or **Visitors**) is the number of distinct visitors who opened the
image. The same report can be grouped or filtered by gene, stage, or publication.
Use the dashboard's top-chart menu and **Export stats** to download the selected
period as CSV for sharing with ZFIN.

Tracking starts with the production deployment containing this feature. Existing
pageviews cannot be backfilled or broken down by image. See the Plausible
[custom event](https://plausible.io/docs/custom-event-goals),
[custom property](https://plausible.io/docs/custom-props/props-dashboard), and
[stats export](https://plausible.io/docs/export-stats) documentation for more
details.

## Rate limiting

gene2image loads images directly from ZFIN's image server (hotlinking). To avoid
triggering ZFIN's per-IP rate limit, images are loaded sequentially with a 150 ms
delay between requests rather than all at once. A grid with 30 images will fully
load in approximately 4–5 seconds — the grid fills in progressively as each image
arrives.

If you do hit a rate limit (images stop loading or show as broken), wait a few
minutes before searching for new genes. Searching for a new gene automatically
cancels any pending loads from the previous search.

## Security / dependency auditing

Dependabot watches the app's real dependencies — Python via the native `uv`
ecosystem (`pyproject.toml` + `uv.lock`) and the frontend via `npm`
(`frontend/package-lock.json`) — and opens update PRs for CVEs
(`.github/dependabot.yml`).

CI hard-gates merges: the **Security Audit** workflow
(`.github/workflows/security-audit.yaml`) fails on high/critical advisories.
Reproduce the same checks locally:

```bash
# Python (audits the same runtime deps the image ships)
uv export --frozen --no-dev --no-emit-project -o /tmp/req.txt && uvx pip-audit -r /tmp/req.txt

# Frontend
cd frontend && npm audit --audit-level=high
```

## Attribution

Images from ZFIN (zfin.org). Thisse et al. in situ hybridization data.
Licensed under CC BY 4.0. Attribution: Thisse, B., Thisse, C. et al.
