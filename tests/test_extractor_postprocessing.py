from app.models import ExtractedTable, TableCell, TableColumn, TableRow
from app.services.documents.extractor import PdfExtractionService


def make_table(table_id: str, bbox: tuple[float, float, float, float], rows: list[list[str]]) -> ExtractedTable:
    return ExtractedTable(
        table_id=table_id,
        page_number=1,
        title=None,
        bbox=bbox,
        columns=[TableColumn(index=index, key=f"col_{index + 1}") for index in range(max(len(row) for row in rows))],
        rows=[
            TableRow(
                index=row_index,
                cells=[
                    TableCell(
                        row=row_index,
                        column=column_index,
                        text=text,
                        bbox=bbox,
                    )
                    for column_index, text in enumerate(row)
                ],
            )
            for row_index, row in enumerate(rows)
        ],
        confidence=0.9,
    )


def test_suppress_duplicate_aggregate_cells_prefers_child_table_rows() -> None:
    service = PdfExtractionService.__new__(PdfExtractionService)
    parent = make_table(
        "p1_t1",
        (0, 0, 100, 100),
        [
            [
                (
                    "Operating cost for the given Volume: (Cost in Rs.)\n"
                    "Cost of Cutting tools 3,63,000\n"
                    "Cost of Tool Holders 22,00,000"
                )
            ]
        ],
    )
    child = make_table(
        "p1_t2",
        (10, 10, 90, 90),
        [
            ["Cost of Cutting tools", "3,63,000"],
            ["Cost of Tool Holders", "22,00,000"],
        ],
    )

    service._suppress_duplicate_aggregate_cells([parent, child], page_number=1)

    assert parent.rows[0].cells[0].text == "Operating cost for the given Volume: (Cost in Rs.)"
    assert parent.warnings[0].code == "duplicate_aggregate_cell_suppressed"
    assert child.rows[0].cells[0].text == "Cost of Cutting tools"


def test_suppress_duplicate_short_summary_cells() -> None:
    service = PdfExtractionService.__new__(PdfExtractionService)
    table = make_table(
        "p1_t1",
        (0, 0, 100, 100),
        [
            ["Cell Cycle Time: 7.00 Total Capital Expenditure 2,97,00,000", "", "", ""],
            ["Cell Cycle Time:", "7.00", "Total Capital Expenditure", "2,97,00,000"],
        ],
    )

    service._suppress_duplicate_aggregate_cells([table], page_number=1)

    assert table.rows[0].cells[0].text == ""
    assert table.warnings[0].code == "duplicate_aggregate_cell_suppressed"


def test_keeps_minor_partial_line_overlap() -> None:
    service = PdfExtractionService.__new__(PdfExtractionService)
    parent = make_table(
        "p1_t1",
        (0, 0, 100, 100),
        [
            [
                (
                    "Assumptions/ Notes:\n"
                    "Refer additional sheet for remarks pertaining to Machining.\n"
                    "Setup changeover time considered included in cycle time."
                )
            ]
        ],
    )
    child = make_table(
        "p1_t2",
        (10, 10, 90, 90),
        [["Setup changeover time considered included in cycle time."]],
    )

    service._suppress_duplicate_aggregate_cells([parent, child], page_number=1)

    assert parent.rows[0].cells[0].text.startswith("Assumptions/ Notes:")
    assert not parent.warnings
