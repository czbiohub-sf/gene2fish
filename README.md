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

## Usage

1. Type a gene symbol (e.g. `pacsin2`, `tbxta`, `pax2a`) in the search box and press Enter
2. The expression grid shows images for each developmental stage where expression data exists
3. Hover an image for a quick summary; click for full metadata
4. Use the stage range slider to narrow the timepoint view
5. Use the anatomy filter to show only images with expression in a specific structure

## Attribution

Images from ZFIN (zfin.org). Thisse et al. in situ hybridization data.
Licensed under CC BY 4.0. Attribution: Thisse, B., Thisse, C. et al.
