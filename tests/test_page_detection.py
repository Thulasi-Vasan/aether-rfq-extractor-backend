from app.models import DocumentExtraction, ExtractedTable, PageMetadata, TableCell, TableRow
from app.services.meridian import MeridianStructuredExtractionService


def _page_meta(page_number: int) -> PageMetadata:
    return PageMetadata(
        page_number=page_number,
        width=100.0,
        height=100.0,
        rotation=0,
        classification="vector_text",
        text_blocks=1,
        text_lines=1,
        text_chars=1,
        image_count=0,
        drawing_count=0,
    )


def _table(table_id: str, page_number: int, title: str, rows: list[list[str]] | None = None) -> ExtractedTable:
    table_rows = []
    for row_index, row in enumerate(rows or [[""]]):
        table_rows.append(
            TableRow(
                index=row_index,
                cells=[
                    TableCell(row=row_index, column=column_index, text=text)
                    for column_index, text in enumerate(row)
                ],
            )
        )
    return ExtractedTable(
        table_id=table_id,
        page_number=page_number,
        title=title,
        bbox=(0.0, 0.0, 100.0, 100.0),
        columns=[],
        rows=table_rows,
        confidence=1.0,
    )


def _blank_rows(row_count: int, col_count: int) -> list[list[str]]:
    return [["" for _ in range(col_count)] for _ in range(row_count)]


def _assembly_rows() -> list[list[str]]:
    rows = _blank_rows(53, 4)
    rows[1][1] = "2425-328"
    rows[2][1] = "CTT"
    rows[25][3] = "12"
    rows[26][3] = "4.5"
    rows[27][3] = "Yes"
    rows[28][3] = "2"
    rows[29][3] = "30"
    return rows


def _removed_page_3_extraction() -> DocumentExtraction:
    return DocumentExtraction(
        document_id="doc",
        filename="removed-page-3.pdf",
        sha256="sha",
        page_count=6,
        pages=[_page_meta(page_number) for page_number in range(1, 7)],
        tables=[
            _table("p1_t1", 1, "SCL-PED RFQ ESTIMATION FOR GRAVITY DIE CASTING (GDC)"),
            _table("p3_t1", 3, "SCL-PED RFQ Process Planning Sheet"),
            _table("p4_t1", 4, "SCL-PED RFQ ESTIMATION FOR ASSEMBLY", _assembly_rows()),
            _table("p5_t1", 5, "SCL-PED RFQ REMARKS"),
            _table("p6_t1", 6, "SCL-PED RFQ ESTIMATION FOR PACKING"),
        ],
    )


def page_by_type(response, page_type: str):
    return next(page for page in response.pages if page.page_type == page_type)


def test_resolve_page_map_with_removed_machining_page() -> None:
    service = MeridianStructuredExtractionService()
    extraction = _removed_page_3_extraction()

    assert service._resolve_page_map(extraction) == {1: 1, 2: 2, 4: 3, 5: 4, 6: 5, 7: 6}


def test_build_dispatches_shifted_assembly_to_logical_page_5() -> None:
    response = MeridianStructuredExtractionService().build(_removed_page_3_extraction())

    assembly = page_by_type(response, "assembly_estimation")
    machining = page_by_type(response, "machining_estimation")

    assert assembly.page_number == 5
    assert assembly.physical_page_number == 4
    assert assembly.header["rfq_no"] == "2425-328"
    assert assembly.assembly_resource_requirements["power_rating_kw_hr"] == 4.5

    assert machining.page_number == 3
    assert machining.physical_page_number is None
    assert machining.machining_operations == []
    assert any(
        warning.code == "meridian_page_not_found"
        and "machining_estimation" in warning.message
        for warning in response.warnings
    )


def test_duplicate_title_first_match_wins_and_warns() -> None:
    extraction = DocumentExtraction(
        document_id="doc",
        filename="duplicate-title.pdf",
        sha256="sha",
        page_count=2,
        pages=[_page_meta(1), _page_meta(2)],
        tables=[
            _table("p1_t1", 1, "SCL-PED RFQ ESTIMATION FOR ASSEMBLY"),
            _table("p2_t1", 2, "SCL-PED RFQ ESTIMATION FOR ASSEMBLY"),
        ],
    )
    service = MeridianStructuredExtractionService()

    assert service._resolve_page_map(extraction)[5] == 1
    assert service._page_resolution_warnings
    assert service._page_resolution_warnings[0].code == "duplicate_meridian_page_signature"
