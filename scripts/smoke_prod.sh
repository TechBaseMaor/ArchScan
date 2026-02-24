#!/usr/bin/env bash
# Production smoke test — run manually to verify deployment health.
# Usage: ./scripts/smoke_prod.sh [API_BASE] [FRONTEND_URL]
#   Default API_BASE:     https://archscan.onrender.com
#   Default FRONTEND_URL: https://archscan-planandgo.netlify.app

set -euo pipefail

API="${1:-https://archscan.onrender.com}"
PASS=0
FAIL=0

check() {
  local label="$1" ; shift
  if "$@" >/dev/null 2>&1; then
    echo "  [PASS] $label"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $label"
    FAIL=$((FAIL + 1))
  fi
}

measure() {
  local label="$1" url="$2"
  local result
  result=$(curl -sS -o /dev/null -w "status=%{http_code} dns=%{time_namelookup}s connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s" --max-time 30 "$url" 2>/dev/null || echo "FAILED")
  echo "  [LATENCY] $label: $result"
}

echo "=== ArchScan Production Smoke Test ==="
echo "API: $API"
echo ""

# 0. Latency measurements
echo "--- Latency ---"
measure "GET /health" "$API/health"
measure "GET /projects" "$API/projects"
echo ""

# 1. Health endpoint reachable
HEALTH=$(curl -sf --max-time 15 "$API/health" 2>/dev/null || echo '{}')
echo "Health response: $HEALTH"
check "Health returns 200" curl -sf --max-time 15 "$API/health"

# 2. Storage is postgres
STORAGE=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('storage',''))" 2>/dev/null || echo "")
check "Storage is postgres" test "$STORAGE" = "postgres"

# 3. Projects endpoint
check "GET /projects returns 200" curl -sf --max-time 10 "$API/projects"

# 4. Rulesets endpoint
check "GET /rulesets returns 200" curl -sf --max-time 10 "$API/rulesets"

# 5. OpenAPI docs accessible
check "GET /docs returns 200" curl -sf --max-time 10 -o /dev/null "$API/docs"

# 6. Projects returns JSON array
check "GET /projects is JSON array" python3 -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('$API/projects'))
assert isinstance(d, list)
"

# 7. CORS preflight returns correct origin
FRONTEND="${2:-https://archscan-planandgo.netlify.app}"
ACAO=$(curl -s -D - -o /dev/null -X OPTIONS \
  -H "Origin: $FRONTEND" \
  -H "Access-Control-Request-Method: GET" \
  "$API/health" 2>/dev/null | grep -i "access-control-allow-origin" | tr -d '\r')
echo "  CORS header: $ACAO"
check "CORS preflight includes frontend origin" bash -c 'echo "$1" | grep -qi -- "$2"' _ "$ACAO" "$FRONTEND"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Troubleshooting hints:"
  [ "$STORAGE" != "postgres" ] && echo "  - DATABASE_URL may be missing in Render Environment"
  echo "$ACAO" | grep -qi "$FRONTEND" || echo "  - ALLOWED_ORIGINS may be missing in Render Environment"
  echo "  - Check Render logs: https://dashboard.render.com"
  echo "  - Check Neon dashboard for connection issues"
  exit 1
fi

echo "All checks passed."
