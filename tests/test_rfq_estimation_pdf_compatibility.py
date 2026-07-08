from pathlib import Path

from app.core.config import Settings
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.cost_estimation.meridian import MeridianStructuredExtractionService
from app.services.documents.extractor import PdfExtractionService
from app.services.rfq_estimation import render_estimation_pdf
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file


def test_generated_rfq_pdf_maps_to_cost_estimation_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "RFQ-654321_estimation.pdf"
    pdf_path.write_bytes(
        render_estimation_pdf(
            {
                "header": {
                    "rfq_no": "RFQ-654321",
                    "date": "2025-02-07",
                    "customer": "Cummins",
                    "final_part_no": "651192",
                    "final_part_rev": "4",
                    "description": "Housing compressor cover",
                    "alloy": "E4-01-240 (C355-T71)",
                    "annual_volume": "33000",
                    "annual_volume_incl_rejection": "37,950",
                }
            }
        )
    )

    settings = Settings(data_dir=tmp_path / "data")
    store = DocumentStore(settings)
    extractor = PdfExtractionService(settings, store)
    digest = sha256_file(pdf_path)
    extraction = extractor.extract_pdf(
        pdf_path,
        document_id=document_id_from_sha256(digest),
        filename=pdf_path.name,
        sha256=digest,
    )

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
    assert not any(record.blocks_approval for record in provenance)
    assert not any(record.null_category == "page_missing" for record in provenance)
    assert sum(1 for record in provenance if record.bbox) > 100
