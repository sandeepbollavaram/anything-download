# Contributing

Thank you for considering a contribution to Anything Download.

## Product rules

- Do not add fake functionality, placeholder download URLs, or success messages
  that hide backend failures.
- Do not implement DRM circumvention, authentication bypass, paywall bypass,
  CAPTCHA bypass, or private-account extraction.
- If a platform cannot be processed legitimately, return a typed error.
- Do not add advertising, tracking SDKs, or analytics by default.
- Do not store user media indefinitely.
- Do not add AI-agent attribution as an author, contributor, or maintainer.

## Development setup

See `docs/local-development.md`.

```bash
# API
cd apps/api
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -e ".[dev]"
pytest

# Web
pnpm install
pnpm --filter @anything-download/web dev
```

Redis is required for the live API and worker. Unit and integration tests use
`fakeredis` and do not need a running Redis server.

## Pull requests

1. Keep changes focused.
2. Add or update tests for behavior you change.
3. Run the relevant quality checks:
   - API: `ruff check`, `ruff format`, `mypy`, `pytest`
   - Web: `pnpm lint`, `pnpm typecheck`, `pnpm build`
4. Do not commit `.env`, secrets, `node_modules`, `.venv`, generated media,
   or editor/AI state files.
5. Do not make default CI depend on live third-party websites. Use fixtures.
   Tests marked `@pytest.mark.external` stay out of the default pipeline.

## Code style

- Python 3.12, Ruff, mypy strict on `src/anything_download`.
- TypeScript, ESLint (`eslint-config-next`), Prettier for the web app.
- User-facing strings belong in copy/catalogue modules, not deep in engines.

## Extractors

Platform extractors live under `apps/api/src/anything_download/extractors/`.
They must:

- detect by hostname/path only
- refuse login-walled, DRM, live, and private content
- expose only formats the source actually advertises
- map failures to typed `ErrorCode` values

## License

By contributing you agree that your contribution is licensed under the MIT
License in `LICENSE`.
