# Anything Download API

Python 3.12 FastAPI service: URL analysis, uploads, job queue, media and
document tools.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn anything_download.main:app --reload --port 8000
```

Workers (same package, different processes):

```bash
python -m anything_download.workers.worker
python -m anything_download.workers.cleanup
```

Tests:

```bash
pytest -q -m "not external and not browser"
```

See the repository `docs/` directory for architecture, security, jobs, and
the HTTP API.
