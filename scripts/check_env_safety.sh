#!/usr/bin/env bash
# Pre-commit / pre-build / pre-deploy safety check for environment files.
#
# Detects:
#   1. Secret-looking values leaked into frontend source
#   2. .env files accidentally staged in git
#   3. Mismatched templates vs validators
#   4. Deploy configuration sanity (netlify.toml, CI flag)
#
# Usage: ./scripts/check_env_safety.sh
# Returns exit 1 if any check fails.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
pass() { echo "  [PASS] $1"; }
warn() { echo "  [WARN] $1"; }

echo "=== ArchScan: ENV + Deploy Safety Check ==="
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

# --- 5. Netlify config sanity ---
echo ""
echo "5. Verifying deploy configuration..."

if [ -f "$ROOT/netlify.toml" ]; then
  pass "netlify.toml exists"

  if grep -q 'npm ci' "$ROOT/netlify.toml" 2>/dev/null; then
    pass "netlify.toml uses 'npm ci' (lockfile-driven install)"
  else
    warn "netlify.toml does not use 'npm ci' — consider switching from 'npm install' for deterministic builds"
  fi

  if grep -q 'context.production' "$ROOT/netlify.toml" 2>/dev/null; then
    pass "netlify.toml has production context defined"
  else
    warn "netlify.toml missing [context.production] — deploy behavior may vary across contexts"
  fi
else
  fail "netlify.toml not found — Netlify deploy will use platform defaults"
fi

# --- 6. Package lockfile exists ---
echo ""
echo "6. Verifying frontend lockfile exists..."

if [ -f "$ROOT/frontend/package-lock.json" ]; then
  pass "frontend/package-lock.json exists (npm ci will work)"
elif [ -f "$ROOT/frontend/yarn.lock" ]; then
  pass "frontend/yarn.lock exists"
else
  fail "No lockfile in frontend/ — npm ci will fail, builds are non-deterministic"
fi

# --- 7. Validate-env script present ---
echo ""
echo "7. Verifying pre-build env validation..."

if [ -f "$ROOT/frontend/scripts/validate-env.js" ]; then
  pass "validate-env.js pre-build guard present"
  if grep -q '"prebuild"' "$ROOT/frontend/package.json" 2>/dev/null; then
    pass "package.json has 'prebuild' script wired"
  else
    fail "package.json missing 'prebuild' script — validate-env.js won't run automatically"
  fi
else
  fail "frontend/scripts/validate-env.js not found — builds may succeed with bad env"
fi

# --- Summary ---
echo ""
echo "=== Results: $FAIL issue(s) found ==="

if [ "$FAIL" -gt 0 ]; then
  echo "Fix the issues above before committing or deploying."
  exit 1
fi

echo "All checks passed."
