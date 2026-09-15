#!/bin/sh
set -eu

role="${1:-api}"

case "$role" in
  api)
    exec python -m uvicorn anything_download.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec python -m anything_download.workers.worker
    ;;
  cleanup)
    exec python -m anything_download.workers.cleanup
    ;;
  *)
    echo "Unknown role: $role (expected api|worker|cleanup)" >&2
    exit 1
    ;;
esac
