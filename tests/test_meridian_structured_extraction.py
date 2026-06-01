import json
from pathlib import Path

from app.models import DocumentExtraction, ExtractedTable, PageMetadata
from app.services.meridian import MeridianStructuredExtractionService, parse_date, parse_int, parse_lbh


def load_sample_extraction() -> DocumentExtraction:
    payload = json.loads(Path("samples/meridian_response.json").read_text(encoding="utf-8"))
    return DocumentExtraction(
        document_id=payload["document_id"],
        filename=payload["filename"],
        sha256="0" * 64,
        page_count=payload["page_count"],
        pages=[
            PageMetadata(
                page_number=page_number,
                width=612,
                height=792,
                rotation=0,
                classification="mixed" if page_number != 2 else "image_only",
                text_blocks=1 if page_number != 2 else 0,
                text_lines=1 if page_number != 2 else 0,
                text_chars=1 if page_number != 2 else 0,
                image_count=1,
                drawing_count=0,
            )
            for page_number in range(1, payload["page_count"] + 1)
        ],
        tables=[ExtractedTable.model_validate(table) for table in payload["tables"]],
        warnings=[],
    )


def page_by_type(response, page_type: str):
    return next(page for page in response.pages if page.page_type == page_type)


def test_parse_helpers() -> None:
    assert parse_date("7-Feb-25") == "2025-02-07"
    assert parse_date("07-Feb-2025") == "2025-02-07"
    assert parse_date("45695") == {
        "raw": "45695",
        "normalized": "2025-02-07",
        "source_format": "excel_serial",
    }
    assert parse_int("2,97,00,000") == 29700000
    assert parse_lbh("242 x211 x134") == {
        "raw": "242 x211 x134",
        "length": 242,
        "breadth": 211,
        "height": 134,
    }


def test_meridian_normalizer_builds_all_page_types() -> None:
    response = MeridianStructuredExtractionService().build(load_sample_extraction())

    assert [page.page_type for page in response.pages] == [
        "gdc_estimation",
        "die_design_feasibility",
        "machining_estimation",
        "machining_process_planning",
        "assembly_estimation",
        "rfq_remarks",
        "packing_estimation",
    ]
    assert len(response.pages) == 7


def test_page_7_packing_arrangements_and_free_text_rows() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "packing_estimation")
    working = page.model_extra["packing_box_quantity_working"]

    assert working["part_size_mm"] == {"length": 242, "breadth": 211, "height": 134}
    assert working["packing_box_size_mm"] == {"length": 1100, "breadth": 910, "height": 1000}
    assert len(working["arrangements"]) == 6
    assert working["arrangements"][1]["no_of_components"] == 120
    assert working["selected_no_of_components_per_box"] == 120
    assert working["selected_arrangement_no"] is None
    assert working["free_text_rows"] == [{"text": "Protection cap to be considered in pricing.", "source": "pdf_text"}]


def test_page_5_preserves_blank_investment_cells_as_null() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "assembly_estimation")
    investments = page.model_extra["assembly_investments"]

    first_item = investments["items"][0]
    assert first_item["description"] == "Assembly station / Fixture"
    assert first_item["capex_rs"] is None
    assert first_item["operating_rs"] is None
    assert investments["total_assembly_investment"] == {"capex_rs": 0.0, "operating_rs": 0.0}


def test_page_3_skips_invalid_rows_and_captures_summaries() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "machining_estimation")

    operations = page.model_extra["machining_operations"]
    assert [operation["operation_no"] for operation in operations] == [20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert page.model_extra["capital_summary"]["total_capital_expenditure_rs"] == 29700000
    assert page.model_extra["cell_summary"]["cell_utilisation_percent"] == 83
    assert page.model_extra["operating_costs"][0]["total_operating_cost_rs"] == 5906162
    assert any(warning.code == "invalid_operation_row" for warning in page.warnings)


def test_page_1_captures_die_details() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "gdc_estimation")
    die_details = page.model_extra["die_details"]

    assert [group["category"] for group in page.model_extra["operating_costs"]] == [
        "Sand core",
        "Casting",
        "Post Casting",
        "Common Facilities",
        "Die",
    ]
    assert die_details["no_of_dies"] == 1
    assert die_details["die_life_shots"] == 50000
    assert die_details["core_box_life_shots"] == 50000
    assert die_details["items"][0]["description"].startswith("Die and corebox")
    assert die_details["operating_items"][0]["description"] == "HT Batch Code Punching Fixture"


def test_page_6_remarks_and_deferred_email_evidence() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "rfq_remarks")

    sections = page.model_extra["remarks_sections"]
    assert [section["section_type"] for section in sections] == ["casting", "machining", "assembly"]
    assert sections[0]["numbered_points"][0]["text"] == "Special sand core cost : Rs. 110/kg"
    assert page.model_extra["email_evidence"][0]["extraction_status"] == "vision_llm_deferred"
    assert any(warning.code == "email_screenshot_deferred" for warning in page.warnings)
