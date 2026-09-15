# syntax=docker/dockerfile:1.7
FROM python:3.14-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# `apt-get upgrade` applies Debian security fixes to packages inherited from the base
# image (a scan found fixable HIGH CVEs in libpcre2 without it).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

WORKDIR /app

FROM base AS builder
COPY apps/api/pyproject.toml apps/api/README.md /src/apps/api/
COPY apps/api/src /src/apps/api/src
WORKDIR /src/apps/api
RUN python -m pip install --upgrade pip \
    && python -m pip install --prefix=/install .

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY apps/api/src /app/src
ENV PYTHONPATH=/app/src \
    AD_STORAGE_DIR=/data \
    AD_FFMPEG_BIN=ffmpeg \
    AD_FFPROBE_BIN=ffprobe

COPY docker/api-entrypoint.sh /usr/local/bin/entrypoint.sh
# Strip CRs: a Windows working tree that has not been normalized by .gitattributes would
# otherwise ship "#!/bin/sh\r" and every API container would fail to start.
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /data \
    && chown -R app:app /data /app

USER app
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["api"]
