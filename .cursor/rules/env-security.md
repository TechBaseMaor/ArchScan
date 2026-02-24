# ENV Security Policy for Claude / Cursor Agents

## NEVER do these

- Never write real secrets (API keys, tokens, passwords, DB connection strings) into source code, comments, logs, or any tracked file.
- Never create or modify `.env` files with production secrets. Use `.env.example` templates with placeholder values only.
- Never add `VITE_SECRET*`, `VITE_API_KEY*`, `VITE_TOKEN*`, `VITE_PASSWORD*`, `VITE_DATABASE*`, or `VITE_PRIVATE*` environment variables. These would be exposed in the browser bundle.
- Never log `DATABASE_URL` or any credential in full. Use `_mask_url()` from `src/app/config.py`.
- Never commit `.env` files. Only `.env.example` templates are tracked.

## ALWAYS do these

- Use `.env.example` as the template for local setup. Real `.env` files are gitignored.
- For new backend secrets: add them to `src/app/config.py` (read from `os.environ`), document in `.env.example` with a placeholder, and instruct the user to set them in Render dashboard.
- For new frontend config: only use `VITE_*` vars that contain non-secret, public values (URLs, feature flags). Add to `frontend/.env.example`.
- Run `./scripts/check_env_safety.sh` before suggesting a commit.
- When creating env-related code, ensure `frontend/scripts/validate-env.js` covers the new var if it's required for production.

## File reference

| File | Purpose |
|------|---------|
| `.env.example` | Backend env template (tracked) |
| `frontend/.env.example` | Frontend env template (tracked) |
| `.env`, `frontend/.env` | Local overrides (gitignored, never commit) |
| `frontend/scripts/validate-env.js` | Build-time frontend env validator |
| `scripts/check_env_safety.sh` | Pre-commit safety scanner |
| `scripts/init_env.sh` | Local .env generator from templates |
| `src/app/config.py` | Backend env reader with production validation |
