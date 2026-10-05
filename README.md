# gene2fish

Zebrafish gene expression image browser. Browse Thisse in situ hybridization images from ZFIN by gene symbol and developmental stage.

Images originate from ZFIN (zfin.org) under CC BY 4.0. To stay resilient to
temporary ZFIN outages, images are served through the backend `/api/image-proxy`
endpoint from our own S3 mirror of the Thisse image package ZFIN provided. An
image that isn't mirrored is loaded by the browser directly from zfin.org; the
backend never fetches from ZFIN. See [Image mirror](#image-mirror).

## Ownership

gene2fish is owned by the [Software Engineering team](https://github.com/orgs/czbiohub-sf/teams/software-engineering) at CZ Biohub SF and maintained by [@NetoRutes](https://github.com/NetoRutes). Pull requests are routed to the maintainer automatically through [`.github/CODEOWNERS`](.github/CODEOWNERS). For questions, bug reports, or access to the deployed app, open an issue in this repo or reach out to the Software Engineering team.

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

`zfin_image_metadata_extractor.py` downloads the 15 required TSVs from ZFIN, joins them, and writes `image_metadata.json` + `image_metadata.tsv` + `gene_aliases.json` + `anatomy_ontology.json`. Pick a directory where the data should live (e.g. `~/projects/gene2image_data`) and run the extractor from there:

```bash
mkdir -p /path/to/gene2image_data
cd /path/to/gene2image_data
uv run python /path/to/gene2image/zfin_image_metadata_extractor.py
```

By default the extractor:
- Downloads the 15 ZFIN TSV files into `./zfin_data/` (skipped if already present)
- Filters to the 5 Thisse publications (`ZDB-PUB-040907-1`, `ZDB-PUB-010810-1`, `ZDB-PUB-051025-1`, `ZDB-PUB-080227-22`, `ZDB-PUB-080220-1`)
- Writes `image_metadata.json` and `image_metadata.tsv` to the current working directory
- Writes `gene_aliases.json` (next to the JSON index): each in-dataset gene's stable ZFIN ID mapped to its previous/alias names (from ZFIN's `aliases.txt`), so the backend can resolve searches by older names (e.g. `oct4` → `pou5f3`). The backend loads it automatically when present; absent, gene search degrades to current symbols only.
- Writes `anatomy_ontology.json` (next to the JSON index): the ZFA substructure hierarchy (`is_a` / `part of` edges from ZFIN's `anatomy_relationship.txt`), so anatomy search can include substructures (e.g. `brain` also finds genes annotated to `hindbrain`), as ZFIN's own expression search does. Absent, anatomy search degrades to exact-term matching.

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
`/api/image-proxy` endpoint. The deployed buckets hold exactly the Thisse image
package ZFIN provided, which is all we're cleared to host, so the proxy serves
images from S3 only and never fetches from ZFIN itself:

- **Mirrored image:** served from S3. If an `_annot.jpg` isn't mirrored, the
  proxy serves the plain `.jpg` instead.
- **Not mirrored:** the proxy answers 404 and the browser loads the image
  straight from zfin.org (a plain hotlink, which ZFIN permits for the Thisse
  images).
- **S3 unreadable** (credentials, permissions, network): the proxy answers 502
  and logs a warning; the browser falls back to zfin.org the same way.
- **PNG export:** zfin.org sends no CORS headers, so the export uses mirrored
  images only and shows "Image unavailable" for anything else.

**No AWS needed locally.** The proxy reads S3 only when
`GENE2IMAGE_IMAGE_S3_BUCKET` is set. When it's unset (e.g. local dev), nothing is
mirrored: the proxy answers 404 for every image and the browser loads them all
from zfin.org directly.

Backend env vars (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `GENE2IMAGE_IMAGE_S3_BUCKET` | _(unset → S3 disabled)_ | Bucket holding the mirror |
| `GENE2IMAGE_IMAGE_S3_PREFIX` | `gene2fish/zfin-images` | Key prefix within the bucket |
| `GENE2IMAGE_IMAGE_S3_REGION` | `us-west-2` | Bucket region |

The deployment must grant the backend `s3:GetObject` on the bucket/prefix, plus
`s3:ListBucket` on the prefix so a missing object reads as a miss (`NoSuchKey`)
rather than `AccessDenied` (via an IAM role / service account; standard AWS
credential chain). The bucket stays **private** — images are never exposed
publicly; they are streamed through the backend.

### Populating the mirror

The mirror holds exactly the Thisse image package ZFIN provided
(`thisse-images.tar`: 190,141 files covering the 53,759 images of the five
Thisse publications), which is all we're cleared to host; ask the maintainers
for a copy. `zfin_image_mirror.py` uploads that tarball to S3 and never
downloads from zfin.org. It validates every file first and uploads nothing if
any file falls outside the five Thisse publications or the expected layout.
Package paths map 1:1 onto the keys the backend derives from a ZFIN image URL:

```
opt/zfin/loadUp/pubs/{year}/{pub}/{file}             (in the tarball)
https://zfin.org/imageLoadUp/{year}/{pub}/{file}     (what the app requests)
  → s3://{bucket}/{prefix}/imageLoadUp/{year}/{pub}/{file}
```

The run is resumable (objects already present are skipped). It needs
`s3:PutObject` on the prefix plus `s3:ListBucket`, which the deployed
environments don't grant by default, so seeding one needs a reviewed write path
in sfbiohub-infra first. Credentials come from the standard AWS chain.

```bash
python zfin_image_mirror.py --package thisse-images.tar --bucket BUCKET --dry-run  # validate + report only
python zfin_image_mirror.py --package thisse-images.tar --bucket BUCKET
```

Useful flags: `--workers N` (concurrency), `--overwrite` (re-upload existing),
`--prefix` / `--region`.

## Usage

1. Type a gene symbol (e.g. `pacsin2`, `tbxta`, `pax2a`) in the search box and press Enter
2. The expression grid shows images for each developmental stage where expression data exists
3. Hover an image for a quick summary; click for full metadata
4. Use the stage range slider to narrow the timepoint view
5. Use the anatomy gene search to find additional genes expressed in a specific structure; selected genes are added as new columns without filtering images already open in the grid. By default a term also matches its substructures (untick *Include substructures* for exact-term matches), and ZFIN annotations recorded as "expression not found" never count as expression

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

Images are served from our own S3 mirror through the backend proxy, so normal
use never touches ZFIN's image server or its per-IP rate limit. The grid still
loads images through a small client-side queue that releases 4 images every
40 ms, so a large comparison grid fills in progressively instead of firing every
request at once. Starting a new gene or stage search cancels any loads still
queued from the previous one.

An image that isn't in the mirror is loaded by the browser straight from
zfin.org (see [Image mirror](#image-mirror)). Those requests come from each
visitor's own IP, so ZFIN's per-IP limit applies per visitor; if ZFIN starts
refusing them, only images missing from the mirror stop loading. Every fallback
(the next mirrored variant, then the zfin.org hotlink) goes back through the
same queue, so during a mirror outage, when every cell fails at once, the grid
still reaches zfin.org at the queue's pace rather than all at once.

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

## License

The code in this repository is licensed under the [MIT License](LICENSE),
copyright CZ Biohub SF, LLC.

That license covers the code only. The ZFIN in situ hybridization images the app
displays stay under CC BY 4.0 and belong to ZFIN, as described in
[Attribution](#attribution) above.
