import json
from pathlib import Path

from app.models import DocumentExtraction, ExtractedTable, PageMetadata
from app.services.meridian import MeridianStructuredExtractionService, parse_date, parse_int, parse_lbh


def load_sample_extraction() -> DocumentExtraction:
    payload = json.loads(Path("samples/response.json").read_text(encoding="utf-8"))
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
    assert response.raw_tables == []
    assert all(page.raw_tables == [] for page in response.pages)
    assert all(page.raw_text == "" for page in response.pages)
    assert response.pages[0].model_extra["source_refs"] == [
        {
            "table_id": "p1_t1",
            "page_number": 1,
            "title": "SCL-PED RFQ ESTIMATION FOR GRAVITY DIE CASTING (GDC)",
        }
    ]


def test_meridian_normalizer_can_include_raw_tables() -> None:
    response = MeridianStructuredExtractionService().build(load_sample_extraction(), include_raw=True)

    assert len(response.raw_tables) == 12
    assert len(response.pages[0].raw_tables) == 1
    assert response.pages[0].raw_tables[0].table_id == "p1_t1"


def test_page_7_packing_arrangements_and_free_text_rows() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "packing_estimation")
    working = page.model_extra["packing_box_quantity_working"]

    assert working["part_size_mm"] == {"length": 242, "breadth": 211, "height": 134}
    assert working["packing_box_size_mm"] == {"length": 1100, "breadth": 910, "height": 1000}
    assert len(working["arrangements"]) == 6
    assert working["arrangements"][1]["no_of_components"] == 120
    assert working["selected_no_of_components_per_box"] == 120
    assert working["selected_arrangement_no"] == 2
    assert working["free_text_rows"] == [{"text": "Protection cap to be considered in pricing.", "source": "pdf_text"}]
    assert not any(warning.code == "selected_arrangement_not_inferred" for warning in page.warnings)


def test_page_5_preserves_blank_investment_cells_as_null() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "assembly_estimation")
    investments = page.model_extra["assembly_investments"]

    first_item = investments["items"][0]
    assert first_item["description"] == "Assembly station / Fixture"
    assert first_item["capex_rs"] is None
    assert first_item["operating_rs"] is None
    assert investments["total_assembly_investment"] == {"capex_rs": 0.0, "operating_rs": 0.0}
    assert page.model_extra["assembly_resource_requirements"]["sealant_type"] == "loc tite 648"
    assert {warning.code for warning in page.warnings} == {"suspicious_lbh_value", "non_boolean_after_assembly_flag"}


def test_page_3_skips_invalid_rows_and_captures_summaries() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "machining_estimation")

    operations = page.model_extra["machining_operations"]
    assert [operation["operation_no"] for operation in operations] == [20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert page.model_extra["capital_summary"]["total_capital_expenditure_rs"] == 29700000
    assert page.model_extra["cell_summary"]["cell_utilisation_percent"] == 83
    assert page.model_extra["operating_costs"][0]["total_operating_cost_rs"] == 5906162
    assert len(page.model_extra["assumptions_notes"]) == 6
    assert page.model_extra["assumptions_notes"][0]["text"] == "Refer additional sheet for remarks pertaining to Machining"
    assert any(warning.code == "blank_operation_row" for warning in page.warnings)
    assert any(warning.code == "invalid_operation_row" for warning in page.warnings)


def test_page_1_captures_die_details() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "gdc_estimation")
    die_details = page.model_extra["die_details"]

    assert page.model_extra["output_machine_details"][0] == {
        "operation": "Sand core 1",
        "no_of_cavities_or_loading": 2,
        "cycle_time_min": 5.0,
        "output_per_hr": 24,
    }
    assert [group["category"] for group in page.model_extra["capital_investments"]] == [
        "Sand core",
        "Casting",
        "Post casting",
        "Automation",
        "Others",
        "Common Facilities",
        "Die",
    ]
    assert [group["category"] for group in page.model_extra["operating_costs"]] == [
        "Sand core",
        "Casting",
        "Post Casting",
        "Common Facilities",
        "Die",
    ]
    assert page.model_extra["capital_investments_summary"]["total_investment_rs_lac"] == 397.3
    assert die_details["capital_items"][0]["no_of_dies"] == 1
    assert die_details["life"]["die_life_shots"] == 50000
    assert die_details["life"]["core_box_life_shots"] == 50000
    assert die_details["capital_items"][0]["description"].startswith("Die and corebox")
    assert die_details["operating_items"][0]["description"] == "HT Batch Code Punching Fixture"
    assert die_details["operating_total_rs_lac"] == 21.0
    assert len(page.model_extra["assumptions_notes"]) == 9


def test_page_6_remarks_and_deferred_email_evidence() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "rfq_remarks")

    sections = page.model_extra["remarks_sections"]
    assert [section["section_type"] for section in sections] == ["casting", "machining", "assembly"]
    assert "numbered_points" not in sections[0]
    numbered = [item for item in sections[0]["items"] if item.get("item_type") == "numbered_remark"]
    assert numbered[0]["text"] == "Special sand core cost : Rs. 110/kg"
    assert numbered[0]["number"] == 1
    assert page.model_extra["email_evidence"][0]["extraction_status"] == "vision_llm_deferred"
    assert any(warning.code == "email_screenshot_deferred" for warning in page.warnings)
    assert any(warning.code == "duplicate_machining_remarks" for warning in page.warnings)


def test_page_4_process_sequence_is_deferred_not_hardcoded() -> None:
    page = page_by_type(MeridianStructuredExtractionService().build(load_sample_extraction()), "machining_process_planning")

    sequence = page.model_extra["process_sequences"][0]
    assert sequence["extraction_status"] == "vision_layout_deferred"
    assert sequence["steps"] == []
    assert any(warning.code == "process_sequence_deferred" for warning in page.warnings)


def test_page_3_operation_parser_captures_extra_rows_before_summary() -> None:
    service = MeridianStructuredExtractionService()
    warnings = []
    rows = [
        ["Opn. No.", "Description", "", "Cycle Time", "No of m/cs", "Machine Cost", "No. of Cells", "Amount"],
        ["20", "TURNING CENTER", "", "7.0", "1", "40,00,000", "1", "40,00,000"],
        ["120", "EXTRA HONING OPERATION", "", "3.5", "1", "10,00,000", "1", "10,00,000"],
        ["", "", "Cell Cycle Time:", "7.00", "Total Capital Expenditure", "", "", "50,00,000"],
    ]

    operations = service._page_3_operations(rows, warnings)

    assert [operation["operation_no"] for operation in operations] == [20, 120]
    assert warnings == []


def test_page_5_section_parser_captures_extra_template_rows() -> None:
    service = MeridianStructuredExtractionService()
    rows = [
        ["BEFORE AFM MACHINING ASSEMBLY Capex Operating", "", "", "", ""],
        ["", "", "Capex", "Operating", ""],
        ["Assembly station / Fixture", "", "", "", ""],
        ["Custom extra assembly fixture", "", "10", "20", ""],
        ["Total Assembly Investment", "", "10", "20", ""],
        ["Total Assembly Investment for all cells", "", "10", "20", ""],
    ]

    investments = service._page_5_assembly_investments(rows)

    assert investments["section_title"] == "BEFORE AFM MACHINING ASSEMBLY"
    assert [item["description"] for item in investments["items"]] == [
        "Assembly station / Fixture",
        "Custom extra assembly fixture",
    ]


def test_page_7_arrangement_parser_captures_extra_arrangements() -> None:
    service = MeridianStructuredExtractionService()
    rows = [
        ["Arrangement 7", "", "", "2", "3", "4"],
        ["No. of components", "", "", "24", "", ""],
        ["Arrangement 8", "", "", "3", "3", "4"],
        ["", "", "", "", "", ""],
        ["No. of components", "", "", "36", "", ""],
    ]

    arrangements = service._page_7_arrangements(rows)

    assert [arrangement["arrangement_no"] for arrangement in arrangements] == [7, 8]
    assert [arrangement["no_of_components"] for arrangement in arrangements] == [24, 36]
    assert service._page_7_selected_arrangement_no(arrangements, 36) == 8
