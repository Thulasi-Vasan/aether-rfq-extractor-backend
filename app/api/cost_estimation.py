import io

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_excel_exporter, get_store
from app.core.config import Settings, get_settings
from app.models import FieldProvenance, MeridianExtractionResponse
from app.services.excel_populator import ExcelExportService
from app.services.meridian import MeridianStructuredExtractionService
from app.services.reasoning import BedrockReasoningService
from app.services.storage import DocumentStore

router = APIRouter()


@router.get("/v1/documents/{document_id}/meridian", response_model=MeridianExtractionResponse)
def get_meridian_extraction(
    document_id: str,
    include_raw: bool = Query(default=False),
    store: DocumentStore = Depends(get_store),
) -> MeridianExtractionResponse:
    extraction = store.load_extraction(document_id)
    pdf_path = store.upload_path(document_id)
    return MeridianStructuredExtractionService().build(extraction, pdf_path=pdf_path, include_raw=include_raw)


@router.get("/v1/documents/{document_id}/export-excel", response_class=StreamingResponse)
def export_excel(
    document_id: str,
    store: DocumentStore = Depends(get_store),
    exporter: ExcelExportService = Depends(get_excel_exporter),
) -> StreamingResponse:
    extraction = store.load_extraction(document_id)
    pdf_path = store.upload_path(document_id)
    structured_data = MeridianStructuredExtractionService().build(extraction, pdf_path=pdf_path)
    excel_bytes, provenance = exporter.populate_with_provenance(
        structured_data, extraction, extraction.filename
    )
    store.save_provenance(document_id, provenance)

    filename = f"{extraction.filename.rsplit('.', 1)[0]}_exported.xlsx" if extraction.filename else "exported.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/v1/documents/{document_id}/provenance", response_model=list[FieldProvenance])
def get_provenance(
    document_id: str,
    store: DocumentStore = Depends(get_store),
) -> list[FieldProvenance]:
    store.load_extraction(document_id)  # 404 if document unknown
    records = store.load_provenance(document_id)
    if records is None:
        raise HTTPException(
            status_code=404,
            detail="Provenance not found. Export the Excel file first to generate provenance.",
        )
    return records


@router.post("/v1/documents/{document_id}/provenance/enrich", response_model=list[FieldProvenance])
def enrich_provenance(
    document_id: str,
    store: DocumentStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> list[FieldProvenance]:
    """Call AWS Bedrock to replace mechanical reasons with LLM-generated explanations.

    Requires the Excel export to have been run first (provenance must exist).
    The model used is controlled by AETHER_BEDROCK_MODEL_ID (default: amazon.nova-lite-v1:0).
    AWS credentials must be available in the environment (IAM role, ~/.aws/credentials, or env vars).
    """
    store.load_extraction(document_id)  # 404 if unknown
    records = store.load_provenance(document_id)
    if records is None:
        raise HTTPException(
            status_code=404,
            detail="Provenance not found. Export the Excel file first.",
        )
    extraction = store.load_extraction(document_id)
    service = BedrockReasoningService(
        model_id=settings.bedrock_model_id,
        region=settings.bedrock_region,
    )
    enriched = service.enrich(records, extraction.filename)
    store.save_provenance(document_id, enriched)
    return enriched
