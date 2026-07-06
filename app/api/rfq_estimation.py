"""API handlers for the RFQ Estimation PDF report (frontend Stage 4 output)."""

import io
import logging
import os
import tempfile

from fastapi import File, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.models.rfq_estimation import PartImageResponse, RfqEstimationRequest
from app.services.doc_classifier.cad_renderer import CADRendererService
from app.services.rfq_estimation import render_estimation_pdf

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


async def render_part_image(
    step_file: UploadFile = File(..., description="3D model (STEP/.stp/.step)"),
) -> PartImageResponse:
    """Render a STEP file to a PNG snapshot for the report's "Part Image" slot.

    Reuses the same cadquery-based renderer the document classifier already
    uses for CAD files, so no new native-lib dependency is introduced.
    """
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
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Part image render failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    log.info("Part image render complete: step=%s bytes=%d", step_file.filename, len(base64_png))
    return PartImageResponse(part_image=f"data:image/png;base64,{base64_png}")
