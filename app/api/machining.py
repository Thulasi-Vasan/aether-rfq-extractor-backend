import logging
import os
import tempfile

from fastapi import APIRouter, File, UploadFile
from fastapi.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool

from app.models import MachiningOperationsResponse
from app.services.machining.service import (
    ExtractionError as MachiningExtractionError,
    extract_machining_operations as run_machining_extraction,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/v1/machining/extract-operations", response_model=MachiningOperationsResponse)
async def extract_machining_operations(
    drawing_pdf: UploadFile = File(..., description="2D engineering drawing (PDF)"),
    step_file: UploadFile = File(..., description="3D model (STEP/.stp/.step)"),
) -> MachiningOperationsResponse:
    log.info("Machining extraction request: pdf=%s step=%s", drawing_pdf.filename, step_file.filename)
    pdf_bytes = await drawing_pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty drawing_pdf upload.")

    step_bytes = await step_file.read()
    if not step_bytes:
        raise HTTPException(status_code=400, detail="Empty step_file upload.")

    suffix = os.path.splitext(step_file.filename or "")[1] or ".stp"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(step_bytes)
            tmp_path = tmp.name
        return await run_in_threadpool(run_machining_extraction, pdf_bytes, tmp_path)
    except MachiningExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Machining extraction failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
