from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import LLMOperation, MachiningOperationsResponse


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_document_returns_structured_error() -> None:
    response = client.get("/v1/documents/does-not-exist")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "document_not_found"


def test_reference_document_endpoint() -> None:
    response = client.get("/v1/reference-document")
    assert response.status_code == 200
    payload = response.json()
    assert "configured" in payload
    assert "path" in payload


def test_reference_pdf_extracts_when_present() -> None:
    settings = get_settings()
    if not Path(settings.reference_pdf_path).exists():
        return

    response = client.post("/v1/reference-document/extract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page_count"] == 7
    assert payload["table_count"] >= 1

    tables_response = client.get(f"/v1/documents/{payload['document_id']}/tables?limit=1")
    assert tables_response.status_code == 200
    tables_payload = tables_response.json()
    assert tables_payload["tables"]
    table = tables_payload["tables"][0]
    assert "columns" in table
    assert "rows" in table
    assert "bbox" in table

    meridian_response = client.get(f"/v1/documents/{payload['document_id']}/meridian")
    assert meridian_response.status_code == 200
    meridian_payload = meridian_response.json()
    assert [page["page_type"] for page in meridian_payload["pages"]] == [
        "gdc_estimation",
        "die_design_feasibility",
        "machining_estimation",
        "machining_process_planning",
        "assembly_estimation",
        "rfq_remarks",
        "packing_estimation",
    ]
    assert meridian_payload["raw_tables"] == []
    assert meridian_payload["pages"][0]["raw_tables"] == []
    assert meridian_payload["pages"][0]["source_refs"][0]["table_id"] == "p1_t1"

    raw_meridian_response = client.get(f"/v1/documents/{payload['document_id']}/meridian?include_raw=true")
    assert raw_meridian_response.status_code == 200
    raw_meridian_payload = raw_meridian_response.json()
    assert len(raw_meridian_payload["raw_tables"]) >= 1
    assert len(raw_meridian_payload["pages"][0]["raw_tables"]) == 1


def test_extract_operations_endpoint_returns_operations_only(monkeypatch) -> None:
    def fake_extract(pdf_bytes: bytes, step_path: str) -> MachiningOperationsResponse:
        assert pdf_bytes == b"%PDF-1.4"
        assert Path(step_path).exists()
        return MachiningOperationsResponse(
            model_id="test-model",
            operations=[
                LLMOperation(
                    opn_no=20,
                    operation_name="FINAL INSPECTION USING CMM",
                    operation_description="Inspect the machined part.",
                    why_machine_process="CMM verifies drawing dimensions.",
                    sequence_rationale="Final inspection follows machining.",
                    source_of_truth=[],
                )
            ],
        )

    monkeypatch.setattr("app.main.run_machining_extraction", fake_extract)
    response = client.post(
        "/v1/machining/extract-operations",
        files={
            "drawing_pdf": ("drawing.pdf", b"%PDF-1.4", "application/pdf"),
            "step_file": ("part.step", b"ISO-10303-21", "application/step"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "test-model"
    assert payload["operations"][0]["opn_no"] == 20
    assert "cell_cycle_time_min" not in payload
    assert "total_capex_rs" not in payload
