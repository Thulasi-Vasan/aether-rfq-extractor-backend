from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_extractor, get_store
from app.core.config import Settings, get_settings
from app.models import DocumentSummary, ReferenceDocumentResponse, TablesResponse
from app.services.documents.extractor import PdfExtractionService
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file

router = APIRouter()


@router.post("/v1/documents", response_model=DocumentSummary)
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


@router.get("/v1/documents/{document_id}", response_model=DocumentSummary)
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


@router.get("/v1/documents/{document_id}/tables", response_model=TablesResponse)
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


@router.get("/v1/documents/{document_id}/pages/{page_number}/tables", response_model=TablesResponse)
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


@router.get("/v1/reference-document", response_model=ReferenceDocumentResponse)
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


@router.post("/v1/reference-document/extract", response_model=DocumentSummary)
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


@router.get("/v1/documents/{document_id}/pdf")
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
