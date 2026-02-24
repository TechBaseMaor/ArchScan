#!/usr/bin/env bash
# Pre-commit / pre-build safety check for environment files.
#
# Detects:
#   1. Secret-looking values leaked into frontend source
#   2. .env files accidentally staged in git
#   3. Mismatched templates vs validators
#
# Usage: ./scripts/check_env_safety.sh
# Returns exit 1 if any check fails.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
pass() { echo "  [PASS] $1"; }

echo "=== ArchScan: ENV Safety Check ==="
echo ""

# --- 1. No secrets in frontend source ---
echo "1. Scanning frontend source for secret-looking strings..."

SECRET_PATTERNS='(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|CREDENTIAL|DATABASE_URL)' 
HITS=$(grep -rEn "$SECRET_PATTERNS" "$ROOT/frontend/src/" --include='*.ts' --include='*.tsx' --include='*.js' 2>/dev/null \
  | grep -v 'node_modules' \
  | grep -v '\.example' \
  | grep -v 'validate-env' \
  | grep -v '// ' || true)

if [ -n "$HITS" ]; then
  fail "Potential secrets found in frontend source:"
  echo "$HITS" | head -20
else
  pass "No secret-looking strings in frontend/src/"
fi

# --- 2. No .env files staged in git ---
echo ""
echo "2. Checking git staging area for .env files..."

STAGED_ENV=$(cd "$ROOT" && git diff --cached --name-only 2>/dev/null | grep -E '\.env($|\.)' | grep -v '\.example' || true)

if [ -n "$STAGED_ENV" ]; then
  fail "Sensitive .env files are staged for commit:"
  echo "$STAGED_ENV"
else
  pass "No .env files staged (only .env.example allowed)"
fi

# --- 3. Templates exist ---
echo ""
echo "3. Verifying .env.example templates exist..."

for TPL in "$ROOT/.env.example" "$ROOT/frontend/.env.example"; do
  if [ -f "$TPL" ]; then
    pass "Found $(basename "$TPL") at ${TPL#$ROOT/}"
  else
    fail "Missing template: ${TPL#$ROOT/}"
  fi
done

# --- 4. .gitignore covers .env ---
echo ""
echo "4. Verifying .gitignore blocks .env files..."

if grep -q 'frontend/\.env$' "$ROOT/.gitignore" 2>/dev/null && grep -q '^\.env$' "$ROOT/.gitignore" 2>/dev/null; then
  pass ".gitignore blocks .env files"
else
  fail ".gitignore may not fully block .env files — review .gitignore"
fi

# --- Summary ---
echo ""
echo "=== Results: $FAIL issue(s) found ==="

if [ "$FAIL" -gt 0 ]; then
  echo "Fix the issues above before committing or deploying."
  exit 1
fi

echo "All checks passed."
