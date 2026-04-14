# gene2image

Zebrafish gene expression image browser. Browse Thisse in situ hybridization images from ZFIN by gene symbol and developmental stage.

Images are hotlinked directly from ZFIN (zfin.org) under CC BY 4.0. Never downloaded or proxied.

## Data

The app requires a pre-built JSON index of Thisse images. This file is **not** included in the repository.

Expected location:
```
/path/to/gene2image_data/image_metadata.json
```

Set the `GENE2IMAGE_DATA_DIR` environment variable to the directory containing `image_metadata.json`.

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

1. Type a gene symbol (e.g. `shha`, `fgf8a`, `pax2a`) in the search box and press Enter
2. The expression grid shows images for each developmental stage where expression data exists
3. Hover an image for a quick summary; click for full metadata
4. Use the stage range slider to narrow the timepoint view
5. Use the anatomy filter to show only images with expression in a specific structure

## Attribution

Images from ZFIN (zfin.org). Thisse et al. in situ hybridization data.
Licensed under CC BY 4.0. Attribution: Thisse, B., Thisse, C. et al.
