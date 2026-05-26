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


def test_part_bundle_upload_extracts_parts_and_relationships() -> None:
    paths = [
        Path("docs/reference-docs/6511292_Rev_4 (3).pdf"),
        Path("docs/reference-docs/6503850_Rev_2 (4).pdf"),
        Path("docs/reference-docs/6543959_Rev_3 (2).pdf"),
        Path("docs/reference-docs/3798675_1 (1).pdf"),
        Path("docs/reference-docs/6511292.stp"),
        Path("docs/reference-docs/6503850.stp"),
        Path("docs/reference-docs/6543959.stp"),
    ]
    if not all(path.exists() for path in paths):
        return

    files = []
    for path in paths:
        media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
        files.append(("files", (path.name, path.read_bytes(), media_type)))

    response = client.post("/v1/part-bundles?force_reextract=true", files=files)
    assert response.status_code == 200
    payload = response.json()

    assert payload["bundle_id"]
    assert {part["part_number"] for part in payload["parts"]} == {"6503850", "6511292", "6543959"}
    relationships = {
        (relationship["parent_part_number"], relationship["child_part_number"])
        for relationship in payload["relationships"]
    }
    assert relationships == {("6511292", "6503850"), ("6543959", "3798675")}
    assert any(warning["code"] == "image_only_pdf" for warning in payload["warnings"])
    assert any(warning["code"] == "child_profile_missing" for warning in payload["warnings"])

    get_response = client.get(f"/v1/part-bundles/{payload['bundle_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["bundle_id"] == payload["bundle_id"]
