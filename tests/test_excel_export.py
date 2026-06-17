import io
from types import SimpleNamespace

import openpyxl
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.core.excel_mapping import CELL_PAGE, EXCEL_MAPPING
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


def test_excel_mapping_prefers_exact_capital_item_match():
    extraction = SimpleNamespace(
        pages=[
            SimpleNamespace(
                capital_investments=[
                    {
                        "category": "Common Facilities",
                        "items": [
                            {"description": "Melting furnace", "amount_per_cell_rs_lac": 80.6},
                            {
                                "description": "Melting furnace accessories (Fork lift, ATL, Degassing unit, Dross trolley, scrubber unit)",
                                "amount_per_cell_rs_lac": 37.0,
                            },
                        ],
                    }
                ]
            )
        ]
    )

    assert EXCEL_MAPPING["M49"](extraction) == 80.6
    assert EXCEL_MAPPING["M50"](extraction) == 37.0


def test_after_assembly_machining_costs_are_normalized_to_lakhs():
    extraction = SimpleNamespace(
        pages=[
            SimpleNamespace(),
            SimpleNamespace(),
            SimpleNamespace(
                operating_costs=[
                    {
                        "category": "machining_operating_cost",
                        "items": [
                            {
                                "description": "Cost of Cutting tools",
                                "amount_rs": 363000,
                            }
                        ],
                    }
                ]
            ),
        ]
    )

    assert EXCEL_MAPPING["AD42"](extraction) == 3.63


def test_capital_total_cost_column_n_has_pdf_fallback_mappings():
    extraction = SimpleNamespace(
        pages=[
            SimpleNamespace(
                capital_investments=[
                    {
                        "category": "Sand core",
                        "items": [
                            {
                                "description": "Core shooting M/c",
                                "total_cost_rs_lac": 47.25,
                            },
                            {
                                "description": "Core placement fixture",
                                "total_cost_rs_lac": 2.1,
                            },
                        ],
                    }
                ],
                capital_investments_summary={
                    "total_investment_rs_lac": 470.765,
                },
            )
        ]
    )

    expected_cells = [f"N{row}" for row in range(23, 55)]
    assert all(coord in EXCEL_MAPPING for coord in expected_cells)
    assert all(CELL_PAGE.get(coord) == 1 for coord in expected_cells)
    assert EXCEL_MAPPING["N23"](extraction) == 47.25
    assert EXCEL_MAPPING["N53"](extraction) == 2.1
    assert EXCEL_MAPPING["N54"](extraction) == 470.765
