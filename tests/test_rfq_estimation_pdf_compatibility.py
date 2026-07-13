import io
from pathlib import Path

import openpyxl
import pytest

from app.core.excel_mapping import EXCEL_MAPPING
from app.core.config import Settings
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.cost_estimation.meridian import MeridianStructuredExtractionService, cell_by_index
from app.services.documents.extractor import PdfExtractionService
from app.services.rfq_estimation import render_estimation_pdf
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file


def _extract(pdf_path: Path, settings: Settings):
    store = DocumentStore(settings)
    extractor = PdfExtractionService(settings, store)
    digest = sha256_file(pdf_path)
    return extractor.extract_pdf(
        pdf_path,
        document_id=document_id_from_sha256(digest),
        filename=pdf_path.name,
        sha256=digest,
    )


def _provenance_source_text(extraction, record) -> str:
    assert record.table_index is not None
    assert record.row_index is not None
    assert record.col_index is not None
    table = extraction.tables[record.table_index]
    source_cell = cell_by_index(table, record.row_index, record.col_index)
    assert source_cell is not None
    return source_cell.text


def test_generated_rfq_pdf_maps_to_cost_estimation_values_and_sources(tmp_path: Path) -> None:
    pdf_path = tmp_path / "RFQ-783214_estimation.pdf"
    pdf_path.write_bytes(
        render_estimation_pdf(
            {
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
        )
    )

    settings = Settings(data_dir=tmp_path / "data")
    extraction = _extract(pdf_path, settings)

    meridian = MeridianStructuredExtractionService()
    assert meridian._resolve_page_map(extraction) == {
        1: 1,
        3: 2,
        4: 3,
        5: 4,
        6: 5,
        7: 6,
    }

    structured = meridian.build(extraction, pdf_path=pdf_path)
    excel_bytes, provenance = ExcelExportService(settings).populate_with_provenance(
        structured,
        extraction,
        pdf_path.name,
    )

    assert excel_bytes
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=False)
    sheet = wb["Input Sheet"]

    expected_cells = {
        "C2": "RFQ-783214",
        "C4": "Creston Mobility",
        "C5": "742681",
        "C7": "Compressor Housing Cover",
        "C8": "E4-01-240 (C355-T71)",
        "G4": 33000,
        "G8": 2.96,
        "G9": 3.8,
        "G10": 242,
        "G11": 211,
        "G12": 134,
        "L12": 2,
        "M12": 5.0,
        "N12": 24,
        "K23": 0.32,
        "L23": 1,
        "M23": 45.0,
        "S15": 2.75,
        "S16": 6.0,
        "S17": 676.0,
        "S19": "Hanger Type",
        "S21": "-",
        "N59": 4.0,
        "N62": 5.8,
        "N63": 6.5,
        "N64": 0.1,
        "N65": 0.8,
        "N69": 17.2,
        "S62": 219.0,
        "R64": "1000 T",
        "S64": 24.6,
        "S65": "Refer Note",
        "S66": "Refer Note",
        "M55": 1,
        "N56": 50000,
        "N57": 50000,
        "AI47": 115.0,
        "AI48": 2.0,
        "AI49": 226.0,
        "AI50": 0.0,
        "AI51": "N",
        "AI52": 1,
        "AQ18": "TURNING CENTER- Diffuser & Inlet M/cng (LT-20)",
        "AS18": 7.0,
        "AT18": 1,
        "AU18": 4000000,
        "AV18": 1,
    }
    for coord, expected in expected_cells.items():
        assert sheet[coord].value == expected

    records = {record.excel_cell: record for record in provenance}
    expected_source_text = {
        "C2": "RFQ-783214",
        "C4": "Creston Mobility",
        "C5": "742681",
        "C7": "Compressor Housing Cover",
        "C8": "E4-01-240 (C355-T71)",
        "G4": "33000",
        "G8": "2.960",
        "G9": "3.800",
        "L12": "2",
        "M12": "5.0",
        "N12": "24",
        "K23": "32%",
        "M23": "45.0",
        "S19": "Hanger Type",
        "S66": "Refer Note",
        "AI47": "115.0",
        "AU18": "40,00,000",
        "AV18": "1",
    }
    for coord, expected in expected_source_text.items():
        assert _provenance_source_text(extraction, records[coord]) == expected

    assert not any(record.blocks_approval for record in provenance)
    assert not any(record.null_category == "page_missing" for record in provenance)
    assert sum(1 for record in provenance if record.bbox) > 100


def test_client_meridian_pdf_keeps_known_cost_estimation_values(tmp_path: Path) -> None:
    pdf_path = Path("samples/2425-328-Meridian-Housing comp-GDC es pdf2323.pdf")
    if not pdf_path.exists():
        pytest.skip("Local Meridian client sample is not checked in.")

    settings = Settings(data_dir=tmp_path / "data")
    extraction = _extract(pdf_path, settings)
    structured = MeridianStructuredExtractionService().build(extraction, pdf_path=pdf_path)

    expected_values = {
        "C2": "2425-328",
        "C4": "CTT",
        "C5": "6511292",
        "G4": 33000,
        "L12": 2,
        "M12": 5.0,
        "N12": 24,
        "K23": 0.32,
        "L23": 1,
        "M23": 45.0,
        "S15": 2.75,
        "S16": 6.0,
        "S17": 676.0,
        "S19": "Hanger Type",
        "S21": "-",
        "S62": 219.0,
        "R64": "1000 T",
        "S64": 24.6,
        "S65": "Refer Note",
        "S66": "Refer Note",
        "M55": 1,
        "N56": 50000,
        "N57": 50000,
        "AI47": 115.0,
        "AI48": 2.0,
        "AI49": 226.0,
        "AU18": 4000000,
        "AV18": 1,
    }
    for coord, expected in expected_values.items():
        assert EXCEL_MAPPING[coord](structured) == expected
