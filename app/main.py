import io
import logging
import os
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Query, UploadFile
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from app.core.config import Settings, get_settings
from app.models import (
    DocumentSummary,
    ErrorResponse,
    FieldProvenance,
    MachiningOperationsResponse,
    MeridianExtractionResponse,
    ReferenceDocumentResponse,
    TablesResponse,
)
from app.services.errors import DocumentNotFoundError, ExtractorError
from app.services.extractor import PdfExtractionService
from app.services.meridian import MeridianStructuredExtractionService
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file
from app.services.excel_populator import ExcelExportService
from app.services.reasoning import BedrockReasoningService
from app.services.machining.service import (
    ExtractionError as MachiningExtractionError,
    extract_machining_operations as run_machining_extraction,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Aether RFQ Extractor Backend", version="0.1.0")

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ExtractorError)
    async def extractor_error_handler(_, exc: ExtractorError) -> JSONResponse:
        payload = ErrorResponse(
            error={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def fastapi_http_error_handler(request, exc: HTTPException):
        return await http_exception_handler(request, exc)

    return app


app = create_app()


def get_store(settings: Settings = Depends(get_settings)) -> DocumentStore:
    return DocumentStore(settings)


def get_extractor(
    settings: Settings = Depends(get_settings),
    store: DocumentStore = Depends(get_store),
) -> PdfExtractionService:
    return PdfExtractionService(settings, store)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/machining/extract-operations", response_model=MachiningOperationsResponse)
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

@app.post("/v1/documents", response_model=DocumentSummary)
async def upload_document(
    file: UploadFile = File(...),
    force_reextract: bool = Query(default=False),
    extractor: PdfExtractionService = Depends(get_extractor),
) -> DocumentSummary:
    temp_path = await extractor.save_upload_to_temp(file)
    try:
        extraction, cached = await run_in_threadpool(
            extractor.extract_upload,
            temp_path,
            file.filename or "upload.pdf",
            force_reextract=force_reextract,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    return DocumentSummary(
        document_id=extraction.document_id,
        filename=extraction.filename,
        page_count=extraction.page_count,
        table_count=len(extraction.tables),
        cached=cached,
        warnings=extraction.warnings,
    )


@app.get("/v1/documents/{document_id}", response_model=DocumentSummary)
def get_document(document_id: str, store: DocumentStore = Depends(get_store)) -> DocumentSummary:
    extraction = store.load_extraction(document_id)
    return DocumentSummary(
        document_id=extraction.document_id,
        filename=extraction.filename,
        page_count=extraction.page_count,
        table_count=len(extraction.tables),
        cached=True,
        warnings=extraction.warnings,
    )


@app.get("/v1/documents/{document_id}/tables", response_model=TablesResponse)
def get_document_tables(
    document_id: str,
    page_number: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_debug: bool = Query(default=False),
    store: DocumentStore = Depends(get_store),
) -> TablesResponse:
    del include_debug
    extraction = store.load_extraction(document_id)
    tables = extraction.tables
    if page_number is not None:
        tables = [table for table in tables if table.page_number == page_number]
    if offset:
        tables = tables[offset:]
    if limit is not None:
        tables = tables[:limit]
    return TablesResponse(
        document_id=extraction.document_id,
        filename=extraction.filename,
        page_count=extraction.page_count,
        tables=tables,
        warnings=extraction.warnings,
    )


@app.get("/v1/documents/{document_id}/pages/{page_number}/tables", response_model=TablesResponse)
def get_page_tables(
    document_id: str,
    page_number: int,
    store: DocumentStore = Depends(get_store),
) -> TablesResponse:
    extraction = store.load_extraction(document_id)
    tables = [table for table in extraction.tables if table.page_number == page_number]
    return TablesResponse(
        document_id=extraction.document_id,
        filename=extraction.filename,
        page_count=extraction.page_count,
        tables=tables,
        warnings=extraction.warnings,
    )


@app.get("/v1/documents/{document_id}/meridian", response_model=MeridianExtractionResponse)
def get_meridian_extraction(
    document_id: str,
    include_raw: bool = Query(default=False),
    store: DocumentStore = Depends(get_store),
) -> MeridianExtractionResponse:
    extraction = store.load_extraction(document_id)
    pdf_path = store.upload_path(document_id)
    return MeridianStructuredExtractionService().build(extraction, pdf_path=pdf_path, include_raw=include_raw)


@app.get("/v1/reference-document", response_model=ReferenceDocumentResponse)
def get_reference_document(
    settings: Settings = Depends(get_settings),
    store: DocumentStore = Depends(get_store),
) -> ReferenceDocumentResponse:
    path = settings.reference_pdf_path
    if not path.exists():
        return ReferenceDocumentResponse(
            configured=False,
            path=str(path),
            message="Reference PDF path does not exist.",
        )

    digest = sha256_file(Path(path))
    document_id = document_id_from_sha256(digest)
    return ReferenceDocumentResponse(
        configured=True,
        path=str(path),
        document_id=document_id,
        extracted=store.has_extraction(document_id),
    )

@app.post("/v1/reference-document/extract", response_model=DocumentSummary)
async def extract_reference_document(
    force_reextract: bool = Query(default=False),
    extractor: PdfExtractionService = Depends(get_extractor),
) -> DocumentSummary:
    extraction, cached = await run_in_threadpool(
        extractor.extract_reference,
        force_reextract=force_reextract,
    )
    return DocumentSummary(
        document_id=extraction.document_id,
        filename=extraction.filename,
        page_count=extraction.page_count,
        table_count=len(extraction.tables),
        cached=cached,
        warnings=extraction.warnings,
    )


def get_excel_exporter(settings: Settings = Depends(get_settings)) -> ExcelExportService:
    return ExcelExportService(settings)


@app.get("/v1/documents/{document_id}/export-excel", response_class=StreamingResponse)
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


@app.get("/v1/documents/{document_id}/provenance", response_model=list[FieldProvenance])
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

@app.post("/v1/documents/{document_id}/provenance/enrich", response_model=list[FieldProvenance])
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


@app.get("/v1/documents/{document_id}/pdf")
def get_document_pdf(
    document_id: str,
    store: DocumentStore = Depends(get_store),
) -> StreamingResponse:
    store.load_extraction(document_id)  # 404 if document unknown
    pdf_path = store.upload_path(document_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found.")
    extraction = store.load_extraction(document_id)
    filename = extraction.filename or f"{document_id}.pdf"
    return StreamingResponse(
        pdf_path.open("rb"),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

