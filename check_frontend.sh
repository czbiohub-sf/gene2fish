#!/usr/bin/env bash
set -e

echo "=== Backend health check ==="
curl -sf http://localhost:8000/api/stages | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK: {len(d)} stages')"

echo "=== Frontend health check ==="
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173)
echo "Frontend HTTP status: $STATUS"
