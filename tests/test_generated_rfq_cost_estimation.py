from pathlib import Path

from app.api.cost_estimation import get_meridian_extraction, get_provenance
from app.core.config import Settings
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.documents.extractor import PdfExtractionService
from app.services.rfq_estimation.cost_estimation_bridge import (
    GeneratedRfqCostEstimationService,
    rfq_payload_hash,
)
from app.services.storage import DocumentStore

# Same generated-RFQ payload already validated in test_rfq_estimation_pdf_compatibility.py:
# produces a clean extraction with page 2 (die design feasibility) legitimately absent.
GENERATED_RFQ_OVERRIDES = {
    "header": {
        "rfq_no": "RFQ-783214",
        "date": "2026-07-10",
        "customer": "Creston Mobility",
        "final_part_no": "742681",
        "final_part_rev": "3",
        "description": "Compressor Housing Cover",
        "alloy": "E4-01-240 (C355-T71)",
        "annual_volume": "33000",
        "annual_volume_incl_rejection": "37,950",
    }
}


def _service(tmp_path: Path) -> tuple[GeneratedRfqCostEstimationService, DocumentStore, Settings]:
    settings = Settings(data_dir=tmp_path / "data")
    store = DocumentStore(settings)
    return GeneratedRfqCostEstimationService(settings, store), store, settings


def test_approval_triggers_cost_estimation_and_reports_page_map(tmp_path: Path) -> None:
    service, store, _ = _service(tmp_path)

    result = service.run(GENERATED_RFQ_OVERRIDES)

    assert result["rfq_payload_hash"] == rfq_payload_hash(GENERATED_RFQ_OVERRIDES)
    assert result["cached"] is False
    assert result["status"] == "success"
    assert result["document_id"]
    assert result["page_map"] == {1: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}
    assert result["blocking_fields"] == []
    assert result["error"] is None
    assert store.has_extraction(result["document_id"])
    assert store.load_provenance(result["document_id"]) is not None


def test_missing_optional_page_two_does_not_block(tmp_path: Path) -> None:
    service, _store, _ = _service(tmp_path)

    result = service.run(GENERATED_RFQ_OVERRIDES)

    # Generated RFQ PDFs legitimately omit page 2 (die design feasibility).
    assert 2 not in result["page_map"]
    assert result["status"] == "success"
    assert result["blocking_fields"] == []


def test_repeated_approval_is_idempotent(tmp_path: Path) -> None:
    service, _store, settings = _service(tmp_path)

    first = service.run(GENERATED_RFQ_OVERRIDES)
    second = service.run(GENERATED_RFQ_OVERRIDES)

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["document_id"] == first["document_id"]
    assert second["status"] == first["status"]
    assert second["page_map"] == first["page_map"]
    # Re-approving the same RFQ must not mint a second document (WeasyPrint stamps a
    # render timestamp, so re-rendering would otherwise produce a different sha256/document_id
    # every time even though the payload is unchanged).
    assert len(list(settings.uploads_dir.glob("*.pdf"))) == 1


def test_failed_extraction_preserves_generated_pdf_reference(tmp_path: Path, monkeypatch) -> None:
    service, store, _ = _service(tmp_path)

    def boom(self, structured, extraction, filename):
        raise RuntimeError("simulated export failure")

    monkeypatch.setattr(ExcelExportService, "populate_with_provenance", boom)

    result = service.run(GENERATED_RFQ_OVERRIDES)

    assert result["status"] == "failed"
    assert result["document_id"]
    assert result["error"]["message"] == "simulated export failure"
    # The generated PDF and its extraction must survive a downstream pipeline failure.
    assert store.upload_path(result["document_id"]).exists()
    assert store.has_extraction(result["document_id"])


def test_manual_document_upload_flow_is_unaffected(tmp_path: Path) -> None:
    """The pre-existing manual `/v1/documents` upload path must keep working unchanged,
    and the existing meridian/provenance route logic must work the same way against a
    document produced by the new automatic RFQ -> cost estimation flow.
    """
    service, store, settings = _service(tmp_path)
    result = service.run(GENERATED_RFQ_OVERRIDES)
    document_id = result["document_id"]

    meridian_response = get_meridian_extraction(document_id, include_raw=False, store=store)
    assert meridian_response.document_id == document_id
    assert [page.page_type for page in meridian_response.pages] == [
        "gdc_estimation",
        "die_design_feasibility",
        "machining_estimation",
        "machining_process_planning",
        "assembly_estimation",
        "rfq_remarks",
        "packing_estimation",
    ]

    provenance = get_provenance(document_id, store=store)
    assert provenance

    manual_pdf = Path("samples/2425-328-Meridian-Housing comp-GDC es pdf2323.pdf")
    if not manual_pdf.exists():
        return

    extractor = PdfExtractionService(settings, store)
    extraction, cached = extractor.extract_upload(manual_pdf, manual_pdf.name)
    assert cached is False
    assert extraction.document_id != document_id
