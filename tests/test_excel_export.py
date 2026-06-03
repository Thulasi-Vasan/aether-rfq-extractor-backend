import io
import openpyxl
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.services.storage import document_id_from_sha256, sha256_file


def test_excel_export():
    client = TestClient(app)
    settings = get_settings()
    
    # ensure reference pdf exists
    ref_path = settings.reference_pdf_path
    if not ref_path.exists():
        return
        
    doc_id = document_id_from_sha256(sha256_file(ref_path))
    
    # Pre-extract if necessary
    client.post("/v1/reference-document/extract")
    
    # Export excel
    response = client.get(f"/v1/documents/{doc_id}/export-excel")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Verify content
    wb = openpyxl.load_workbook(io.BytesIO(response.content), data_only=True)
    assert "Input Sheet" in wb.sheetnames
    sheet = wb["Input Sheet"]
    
    # Basic assertions from our mapping
    assert sheet["C2"].value == "2425-328" # rfq_no
    assert sheet["C10"].value == "Domestic"
