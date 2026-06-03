import io
from pathlib import Path

from fastapi import Depends, FastAPI, File, Query, UploadFile
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.models import (
    DocumentSummary,
    ErrorResponse,
    MeridianExtractionResponse,
    ReferenceDocumentResponse,
    TablesResponse,
)
from app.services.errors import DocumentNotFoundError, ExtractorError
from app.services.extractor import PdfExtractionService
from app.services.meridian import MeridianStructuredExtractionService
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file
from app.services.excel_populator import ExcelExportService


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
    excel_bytes = exporter.populate(structured_data)
    
    filename = f"{extraction.filename.rsplit('.', 1)[0]}_exported.xlsx" if extraction.filename else "exported.xlsx"
    
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

