import io
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_excel_exporter, get_store
from app.core.config import Settings, get_settings
from app.models import FieldProvenance, MeridianExtractionResponse
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.cost_estimation.meridian import MeridianStructuredExtractionService
from app.services.cost_estimation.reasoning import BedrockReasoningService
from app.services.storage import DocumentStore

from fastapi import Depends
from app.api.dependencies import get_current_user
log = logging.getLogger(__name__)


def get_meridian_extraction(
    document_id: str,
    include_raw: bool = Query(default=False),
    store: DocumentStore = Depends(get_store),
) -> MeridianExtractionResponse:
    log.info("Meridian extraction request: document_id=%s include_raw=%s", document_id, include_raw)
    extraction = store.load_extraction(document_id)
    pdf_path = store.upload_path(document_id)
    response = MeridianStructuredExtractionService().build(extraction, pdf_path=pdf_path, include_raw=include_raw)
    log.info(
        "Meridian extraction complete: document_id=%s pages=%d include_raw=%s",
        document_id,
        len(response.pages),
        include_raw,
    )
    return response


def export_excel(
    document_id: str,
    store: DocumentStore = Depends(get_store),
    exporter: ExcelExportService = Depends(get_excel_exporter),
) -> StreamingResponse:
    log.info("Excel export request: document_id=%s", document_id)
    extraction = store.load_extraction(document_id)
    pdf_path = store.upload_path(document_id)
    structured_data = MeridianStructuredExtractionService().build(extraction, pdf_path=pdf_path)
    excel_bytes, provenance = exporter.populate_with_provenance(
        structured_data, extraction, extraction.filename
    )
    store.save_provenance(document_id, provenance)

    filename = f"{extraction.filename.rsplit('.', 1)[0]}_exported.xlsx" if extraction.filename else "exported.xlsx"
    log.info(
        "Excel export complete: document_id=%s filename=%s bytes=%d provenance_records=%d",
        document_id,
        filename,
        len(excel_bytes),
        len(provenance),
    )
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def get_provenance(
    document_id: str,
    store: DocumentStore = Depends(get_store),
) -> list[FieldProvenance]:
    log.info("Provenance request: document_id=%s", document_id)
    store.load_extraction(document_id)  # 404 if document unknown
    records = store.load_provenance(document_id)
    if records is None:
        log.warning("Provenance not found: document_id=%s", document_id)
        raise HTTPException(
            status_code=404,
            detail="Provenance not found. Export the Excel file first to generate provenance.",
        )
    log.info("Provenance loaded: document_id=%s records=%d", document_id, len(records))
    return records


def enrich_provenance(
    document_id: str,
    store: DocumentStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> list[FieldProvenance]:
    """Call AWS Bedrock to replace mechanical reasons with LLM-generated explanations.

    Requires the Excel export to have been run first (provenance must exist).
    The model used is controlled by AETHER_COST_ESTIMATION_BEDROCK_MODEL_ID.
    AWS credentials must be available in the environment (IAM role, ~/.aws/credentials, or env vars).
    """
    log.info(
        "Provenance enrichment request: document_id=%s model=%s",
        document_id,
        settings.cost_estimation_bedrock_model_id,
    )
    store.load_extraction(document_id)  # 404 if unknown
    records = store.load_provenance(document_id)
    if records is None:
        log.warning("Provenance enrichment skipped, records missing: document_id=%s", document_id)
        raise HTTPException(
            status_code=404,
            detail="Provenance not found. Export the Excel file first.",
        )
    extraction = store.load_extraction(document_id)
    service = BedrockReasoningService(
        model_id=settings.cost_estimation_bedrock_model_id,
        region=settings.bedrock_region,
    )
    enriched = service.enrich(records, extraction.filename)
    store.save_provenance(document_id, enriched)
    changed = sum(1 for before, after in zip(records, enriched) if before.reason != after.reason)
    log.info(
        "Provenance enrichment complete: document_id=%s records=%d updated_reasons=%d",
        document_id,
        len(enriched),
        changed,
    )
    return enriched
