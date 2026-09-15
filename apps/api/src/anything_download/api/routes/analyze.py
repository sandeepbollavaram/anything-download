"""POST /api/v1/analyze: the central URL analysis endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from anything_download.analysis.engine import analyze_url
from anything_download.analysis.models import AnalyzeRequest, URLAnalysis
from anything_download.api.state import AppState, get_state
from anything_download.errors import ErrorResponse
from anything_download.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["analysis"])


@router.post(
    "/analyze",
    response_model=URLAnalysis,
    summary="Analyze a URL",
    description=(
        "Normalizes and validates the URL, detects whether it is a direct file, a webpage or a "
        "supported public media platform, and returns the tools that can be applied. Problems with "
        "the source are reported in `status`/`reason` rather than as HTTP errors."
    ),
    responses={
        400: {"model": ErrorResponse},
        414: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def analyze(
    body: AnalyzeRequest, state: Annotated[AppState, Depends(get_state)]
) -> URLAnalysis:
    result = await analyze_url(body.url, http=state.http, settings=state.settings)
    log.info(
        "analyze",
        url=result.normalized_url,
        source_kind=result.source_kind,
        resource_type=result.resource_type.value,
        status=result.status,
    )
    return result
