from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


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
