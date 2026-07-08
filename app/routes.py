from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

# Import dependencies
from app.api.dependencies import get_current_user

# Import models
from app.api.auth import LoginResponse, UserProfile
from app.api.doc_classification import JobStatusResponse, ZipClassificationResponse
from app.models.classifier import ClassificationResponse
from app.models import DocumentSummary, TablesResponse, ReferenceDocumentResponse, FieldProvenance
from app.api.cost_estimation import MeridianExtractionResponse
from app.api.machining import MachiningOperationsResponse
from app.models.rfq_estimation import PartImageResponse, RfqEstimationRequest

# Import handlers
from app.api.auth import login, get_me
from app.api.doc_classification import classify_document, classify_zip, get_zip_classification_status, get_artifact
from app.api.documents import (
    upload_document, get_document, get_document_tables, get_page_tables,
    get_reference_document, extract_reference_document, get_document_pdf
)
from app.api.cost_estimation import (
    get_meridian_extraction, export_excel, get_provenance, enrich_provenance
)
from app.api.machining import extract_machining_operations
from app.api.rfq_estimation import generate_estimation_pdf, render_part_image

api_router = APIRouter()

# Auth routes (Unprotected / Partially protected)
auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])
auth_router.add_api_route("/login", login, methods=["POST"], response_model=LoginResponse)
auth_router.add_api_route("/me", get_me, methods=["GET"], response_model=UserProfile)
api_router.include_router(auth_router)

# Protected routes
protected_router = APIRouter(dependencies=[Depends(get_current_user)])

# Document Classification
protected_router.add_api_route("/v1/documents/classify", classify_document, methods=["POST"], response_model=ClassificationResponse)
protected_router.add_api_route("/v1/documents/classify-zip", classify_zip, methods=["POST"], response_model=JobStatusResponse)
protected_router.add_api_route("/v1/documents/classify-zip/{job_id}", get_zip_classification_status, methods=["GET"], response_model=JobStatusResponse)
protected_router.add_api_route("/v1/documents/artifacts/{job_id}/{filename}", get_artifact, methods=["GET"])

# Documents
protected_router.add_api_route("/v1/documents", upload_document, methods=["POST"], response_model=DocumentSummary)
protected_router.add_api_route("/v1/documents/{document_id}", get_document, methods=["GET"], response_model=DocumentSummary)
protected_router.add_api_route("/v1/documents/{document_id}/tables", get_document_tables, methods=["GET"], response_model=TablesResponse)
protected_router.add_api_route("/v1/documents/{document_id}/pages/{page_number}/tables", get_page_tables, methods=["GET"], response_model=TablesResponse)
protected_router.add_api_route("/v1/reference-document", get_reference_document, methods=["GET"], response_model=ReferenceDocumentResponse)
protected_router.add_api_route("/v1/reference-document/extract", extract_reference_document, methods=["POST"], response_model=DocumentSummary)
protected_router.add_api_route("/v1/documents/{document_id}/pdf", get_document_pdf, methods=["GET"])

# Cost Estimation
protected_router.add_api_route("/v1/documents/{document_id}/meridian", get_meridian_extraction, methods=["GET"], response_model=MeridianExtractionResponse)
protected_router.add_api_route("/v1/documents/{document_id}/export-excel", export_excel, methods=["GET"], response_class=StreamingResponse)
protected_router.add_api_route("/v1/documents/{document_id}/provenance", get_provenance, methods=["GET"], response_model=list[FieldProvenance])
protected_router.add_api_route("/v1/documents/{document_id}/provenance/enrich", enrich_provenance, methods=["POST"], response_model=list[FieldProvenance])

# Machining
protected_router.add_api_route("/v1/machining/extract-operations", extract_machining_operations, methods=["POST"], response_model=MachiningOperationsResponse)

# RFQ Estimation report (Stage 4 — 7-page SCL-PED estimation PDF)
protected_router.add_api_route("/v1/rfq-estimation/pdf", generate_estimation_pdf, methods=["POST"], response_class=StreamingResponse)
protected_router.add_api_route("/v1/rfq-estimation/part-image", render_part_image, methods=["POST"], response_model=PartImageResponse)

api_router.include_router(protected_router)
