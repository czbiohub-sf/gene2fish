#!/usr/bin/env bash
set -e

BASE="http://localhost:8000"

echo "=== Stages endpoint ==="
STAGES=$(curl -sf "$BASE/api/stages")
COUNT=$(echo "$STAGES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "Stages: $COUNT"
[ "$COUNT" -eq 37 ] && echo "PASS" || echo "WARN: expected 37 stages, got $COUNT"

echo ""
echo "=== Gene search ==="
RESULTS=$(curl -sf "$BASE/api/genes/search?q=shh")
echo "Results for 'shh': $RESULTS"

echo ""
echo "=== Gene images (fgf8a) ==="
IMAGES=$(curl -sf "$BASE/api/genes/fgf8a/images")
IMG_COUNT=$(echo "$IMAGES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "Images for fgf8a: $IMG_COUNT"
[ "$IMG_COUNT" -gt 0 ] && echo "PASS" || echo "FAIL: expected images for fgf8a"

echo ""
echo "=== Image URL format check ==="
echo "$IMAGES" | python3 -c "
import sys, json
images = json.load(sys.stdin)
if images:
    url = images[0]['image_url']
    print(f'Sample URL: {url}')
    assert 'zfin.org' in url, 'URL must point to zfin.org'
    assert '_annot.jpg' in url, 'URL should use _annot.jpg'
    print('PASS')
"

echo ""
echo "=== Anatomy search ==="
ANAT=$(curl -sf "$BASE/api/anatomy/search?q=brain")
echo "Anatomy results for 'brain': $ANAT"

echo ""
echo "=== Batch endpoint ==="
BATCH=$(curl -sf -X POST "$BASE/api/genes/batch" \
  -H "Content-Type: application/json" \
  -d '{"genes": ["shhb", "fgf8a"], "stage_min": null, "stage_max": null, "anatomy": null}')
echo "$BATCH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for gene, imgs in d.items():
    print(f'{gene}: {len(imgs)} images')
"
echo "PASS"
