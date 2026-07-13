"""API handlers for the RFQ Estimation PDF report (frontend Stage 4 output)."""

import io
import logging
import os
import tempfile

from fastapi import Depends, File, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_store
from app.core.config import Settings, get_settings
from app.models.rfq_estimation import (
    GeneratedRfqCostEstimationResponse,
    PartImageResponse,
    RfqEstimationRequest,
)
from app.services.doc_classifier.cad_renderer import CADRendererService
from app.services.rfq_estimation import render_estimation_pdf
from app.services.rfq_estimation.cost_estimation_bridge import GeneratedRfqCostEstimationService
from app.services.storage import DocumentStore

log = logging.getLogger(__name__)


def generate_estimation_pdf(payload: RfqEstimationRequest) -> StreamingResponse:
    """Render the 7-page SCL-PED RFQ Estimation report from stage data.

    The request carries whatever the caller has (typically frontend stages 1-3);
    every unset field falls back to the Meridian reference defaults, so even an
    empty body yields a complete, faithful report.
    """
    overrides = payload.as_overrides()
    log.info("RFQ estimation PDF request: sections=%s", sorted(overrides.keys()))
    pdf_bytes = render_estimation_pdf(overrides)

    header = overrides.get("header") or {}
    rfq_no = str(header.get("rfq_no") or "rfq").replace("/", "-").replace(" ", "_")
    filename = f"{rfq_no}_estimation.pdf"
    log.info("RFQ estimation PDF complete: filename=%s bytes=%d", filename, len(pdf_bytes))

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def trigger_cost_estimation(
    payload: RfqEstimationRequest,
    settings: Settings = Depends(get_settings),
    store: DocumentStore = Depends(get_store),
) -> GeneratedRfqCostEstimationResponse:
    """Auto-run the Cost Estimation flow on a generated RFQ Estimation PDF.

    Called when the frontend approves/finalizes the RFQ Estimation Report (Stage 4):
    renders the same PDF `POST /v1/rfq-estimation/pdf` would, then runs it through the
    existing cost estimation pipeline (extraction, Meridian structuring, Excel/provenance
    export) and returns the resulting `document_id` so the frontend can drive the existing
    `/v1/documents/{document_id}/...` routes for the Cost Estimation and Final Report tabs.

    Idempotent: approving the same RFQ payload again returns the same document_id and
    status rather than creating a duplicate cost document. A pipeline failure still
    returns the generated PDF's document_id (so it can be fetched via the existing
    `/v1/documents/{document_id}/pdf` route) with `status="failed"` and `error` details —
    it never raises, so the generated PDF is never invalidated by a downstream failure.
    """
    overrides = payload.as_overrides()
    log.info("Generated RFQ cost estimation request: sections=%s", sorted(overrides.keys()))
    service = GeneratedRfqCostEstimationService(settings, store)
    result = service.run(overrides)
    log.info(
        "Generated RFQ cost estimation complete: document_id=%s status=%s cached=%s blocking_fields=%d",
        result.get("document_id"),
        result.get("status"),
        result.get("cached"),
        len(result.get("blocking_fields") or []),
    )
    return GeneratedRfqCostEstimationResponse(**result)


async def render_part_image(
    step_file: UploadFile = File(..., description="3D model (STEP/.stp/.step)"),
    settings: Settings = Depends(get_settings),
) -> PartImageResponse:
    """Render a STEP file to a PNG snapshot for the report's "Part Image" slot.

    Reuses the same cadquery-based renderer the document classifier already
    uses for CAD files, so no new native-lib dependency is introduced. Gated by
    Settings.enable_cad_part_image so machines without cadquery installed can
    still run everything else (the main PDF endpoint doesn't need it) — the
    frontend already treats this endpoint as best-effort and falls back to the
    report's placeholder box on any failure.
    """
    if not settings.enable_cad_part_image:
        raise HTTPException(
            status_code=501,
            detail="CAD part-image rendering is disabled (AETHER_ENABLE_CAD_PART_IMAGE=false).",
        )

    step_bytes = await step_file.read()
    if not step_bytes:
        raise HTTPException(status_code=400, detail="Empty step_file upload.")

    suffix = os.path.splitext(step_file.filename or "")[1] or ".stp"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(step_bytes)
            tmp_path = tmp.name
        log.info("Part image render request: step=%s", step_file.filename)
        base64_png = await run_in_threadpool(
            CADRendererService.render_step_to_base64_png, tmp_path
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="cadquery is not installed — set AETHER_ENABLE_CAD_PART_IMAGE=false to hide this feature.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Part image render failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    log.info("Part image render complete: step=%s bytes=%d", step_file.filename, len(base64_png))
    return PartImageResponse(part_image=f"data:image/png;base64,{base64_png}")
