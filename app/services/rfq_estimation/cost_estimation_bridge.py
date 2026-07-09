"""Bridge the generated RFQ Estimation PDF (Stage 4) into the existing Cost Estimation flow.

The generated PDF is treated exactly like a manually uploaded cost RFQ: it is stored via
`DocumentStore` and run through the same `PdfExtractionService` / `MeridianStructuredExtractionService`
/ `ExcelExportService` pipeline used by `POST /v1/documents` + friends. Nothing about the
manual upload flow changes.

WeasyPrint stamps a render timestamp into the PDF bytes, so re-rendering the same RFQ
payload never reproduces the same sha256 — the content-addressed document id the manual
upload flow relies on can't be used as the idempotency key here. Instead we key on a hash
of the RFQ payload itself and persist a small association record (`DocumentStore.
save_generated_rfq_link`) mapping that hash to the resulting cost document id.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.cost_estimation.meridian import MeridianStructuredExtractionService
from app.services.documents.extractor import PdfExtractionService
from app.services.rfq_estimation.renderer import render_estimation_pdf
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file

log = logging.getLogger(__name__)


def rfq_payload_hash(overrides: dict[str, Any]) -> str:
    """Stable hash of an RFQ estimation payload, independent of key order."""
    canonical = json.dumps(overrides, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class GeneratedRfqCostEstimationService:
    """Renders a generated RFQ PDF (if needed) and runs it through cost estimation."""

    def __init__(self, settings: Settings, store: DocumentStore) -> None:
        self.settings = settings
        self.store = store
        self.extractor = PdfExtractionService(settings, store)
        self.exporter = ExcelExportService(settings)

    def run(self, overrides: dict[str, Any]) -> dict[str, Any]:
        payload_hash = rfq_payload_hash(overrides)
        pdf_filename = self._pdf_filename(overrides)

        link = self.store.load_generated_rfq_link(payload_hash)
        if link is not None:
            # JSON object keys are always strings; restore the int keys `_run_pipeline`
            # produced so a cache hit returns the same shape as a fresh run.
            link["page_map"] = {int(key): value for key, value in link.get("page_map", {}).items()}
        document_id = link.get("document_id") if link else None

        if link and link.get("status") == "success" and document_id and self.store.has_extraction(document_id):
            log.info("Generated RFQ cost estimation cache hit: payload_hash=%s document_id=%s", payload_hash, document_id)
            return {**link, "cached": True}

        if document_id and self.store.has_extraction(document_id):
            # A previous attempt for this exact payload got as far as storing the PDF and
            # extraction but failed later in the pipeline (e.g. Excel export). Retry the
            # rest of the pipeline against the same already-generated PDF/document instead
            # of re-rendering — re-rendering would mint a new document id and orphan the
            # first one, which is exactly the duplicate-document outcome we must avoid.
            log.info("Retrying failed generated RFQ cost estimation: payload_hash=%s document_id=%s", payload_hash, document_id)
            extraction = self.store.load_extraction(document_id)
        else:
            pdf_bytes = render_estimation_pdf(overrides)
            document_id, extraction = self._store_generated_pdf(pdf_bytes, pdf_filename)

        record = self._run_pipeline(document_id, extraction, payload_hash, pdf_filename)
        self.store.save_generated_rfq_link(payload_hash, record)
        return {**record, "cached": False}

    def _pdf_filename(self, overrides: dict[str, Any]) -> str:
        header = overrides.get("header") or {}
        rfq_no = str(header.get("rfq_no") or "rfq").replace("/", "-").replace(" ", "_")
        return f"{rfq_no}_estimation.pdf"

    def _store_generated_pdf(self, pdf_bytes: bytes, pdf_filename: str):
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = Path(tmp.name)

            digest = sha256_file(tmp_path)
            document_id = document_id_from_sha256(digest)

            if self.store.has_extraction(document_id):
                return document_id, self.store.load_extraction(document_id)

            upload_path = self.store.save_upload(tmp_path, document_id)
            extraction = self.extractor.extract_pdf(
                upload_path, document_id=document_id, filename=pdf_filename, sha256=digest
            )
            self.store.save_extraction(extraction)
            return document_id, extraction
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    def _run_pipeline(self, document_id: str, extraction, payload_hash: str, pdf_filename: str) -> dict[str, Any]:
        record: dict[str, Any] = {
            "rfq_payload_hash": payload_hash,
            "pdf_filename": pdf_filename,
            "document_id": document_id,
            "status": "failed",
            "page_map": {},
            "warnings": [],
            "blocking_fields": [],
            "error": None,
        }
        try:
            meridian = MeridianStructuredExtractionService()
            structured = meridian.build(extraction, pdf_path=self.store.upload_path(document_id))
            page_map = {
                page.page_number: page.physical_page_number
                for page in structured.pages
                if page.physical_page_number is not None
            }

            _excel_bytes, provenance = self.exporter.populate_with_provenance(
                structured, extraction, extraction.filename
            )
            self.store.save_provenance(document_id, provenance)

            record["page_map"] = page_map
            record["warnings"] = [warning.model_dump(mode="json") for warning in structured.warnings]
            record["blocking_fields"] = [item.excel_cell for item in provenance if item.blocks_approval]
            record["status"] = "failed" if record["blocking_fields"] else "success"
        except Exception as exc:  # noqa: BLE001 - convert any pipeline failure into a structured result
            log.exception("Generated RFQ cost estimation pipeline failed: document_id=%s", document_id)
            record["error"] = {
                "code": getattr(exc, "code", exc.__class__.__name__),
                "message": getattr(exc, "message", str(exc)),
                "details": getattr(exc, "details", {}) or {},
            }
        return record
