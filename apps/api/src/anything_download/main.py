"""ASGI entry point: ``uvicorn anything_download.main:app``."""

from anything_download.api.app import create_app

app = create_app()
