from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import fitz

from app.models import (
    DocumentExtraction,
    ExtractedTable,
    ExtractionWarning,
    MeridianExtractionResponse,
    MeridianStructuredPage,
    TableCell,
    WarningSeverity,
)


EXCEL_DATE_BASE = date(1899, 12, 30)
FORMULA_ERROR_VALUES = {"#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}


def parse_number(value: str | None) -> int | float | None:
    text = clean_text(value)
    if not text or text == "-":
        return None
    text = text.replace(",", "").replace("%", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    number = float(text)
    return int(number) if number.is_integer() else number


def parse_int(value: str | None) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_float(value: str | None) -> float | None:
    number = parse_number(value)
    return float(number) if number is not None else None


def parse_percent(value: str | None) -> float | None:
    text = clean_text(value)
    parsed = parse_float(text)
    if parsed is None:
        return None
    if "%" in text or parsed > 1:
        return parsed / 100
    return parsed


def parse_bool(value: str | None) -> bool | None:
    text = clean_text(value).lower()
    if text in {"yes", "y", "true"}:
        return True
    if text in {"no", "n", "false", "0", "0.0", "-"}:
        return False
    return None


def parse_date(value: str | None) -> dict[str, str | None] | str | None:
    text = clean_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{5}", text):
        normalized = EXCEL_DATE_BASE + timedelta(days=int(text))
        return {
            "raw": text,
            "normalized": normalized.isoformat(),
            "source_format": "excel_serial",
        }
    for fmt in ("%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def parse_lbh(value: str | None) -> dict[str, Any]:
    text = clean_text(value)
    numbers = [int(match) for match in re.findall(r"\d+", text)]
    if len(numbers) >= 3:
        return {"raw": text, "length": numbers[0], "breadth": numbers[1], "height": numbers[2]}
    return {"raw": text or None, "length": None, "breadth": None, "height": None}


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def one_line(value: str | None) -> str:
    return clean_text(value).replace("\n", " ").strip()


def null_if_blank(value: str | None) -> str | None:
    text = clean_text(value)
    return text if text else None


def warning(code: str, message: str, page_number: int, details: dict[str, Any] | None = None) -> ExtractionWarning:
    return ExtractionWarning(
        code=code,
        message=message,
        page_number=page_number,
        severity=WarningSeverity.warning,
        details=details or {},
    )


def matrix(table: ExtractedTable | None) -> list[list[str]]:
    if table is None:
        return []
    return [
        [cell.text for cell in sorted(row.cells, key=lambda cell: cell.column)]
        for row in sorted(table.rows, key=lambda row: row.index)
    ]


def matrix_cells(table: ExtractedTable | None) -> list[list[TableCell | None]]:
    """Like matrix() but returns TableCell objects so bbox is preserved."""
    if table is None:
        return []
    return [
        [cell for cell in sorted(row.cells, key=lambda c: c.column)]
        for row in sorted(table.rows, key=lambda r: r.index)
    ]


def cell_at(cell_rows: list[list[TableCell | None]], row: int, col: int) -> TableCell | None:
    """Safely index into a cell matrix, returning None if out of bounds."""
    if row < 0 or row >= len(cell_rows):
        return None
    r = cell_rows[row]
    if col < 0 or col >= len(r):
        return None
    return r[col]


def cell_by_index(table: ExtractedTable | None, row_index: int, col: int) -> TableCell | None:
    """Find a cell by its REAL TableCell.row / TableCell.column.

    Unlike cell_at (positional), this is robust to rows that omit blank columns,
    so a stored (row, col) source always resolves to the exact same cell/bbox.
    """
    if table is None:
        return None
    for table_row in table.rows:
        for tc in table_row.cells:
            if tc.row == row_index and tc.column == col:
                return tc
    return None


def src(table_id: str, table_cell: TableCell | None) -> dict | None:
    """Build a provenance source descriptor from the exact cell that produced a value.

    Stores the cell's real row/column (not a positional guess); bbox is resolved
    later via cell_by_index to keep the structured JSON lean.
    """
    if table_cell is None:
        return None
    return {"table_id": table_id, "row": table_cell.row, "col": table_cell.column}


def labeled_src(
    str_rows: list[list[str]],
    cells: list[list[TableCell | None]],
    table_id: str,
    label: str,
    value_column: int = 1,
) -> dict | None:
    """Source for a value found by matching `label` in column 0 (mirrors row_value)."""
    for index, row in enumerate(str_rows):
        if row and one_line(row[0]).lower() == label.lower():
            return src(table_id, cell_at(cells, index, value_column))
    return None


def find_text_in_tables(
    tables: list[ExtractedTable], search_text: str, *, page_number: int | None = None
) -> tuple[ExtractedTable, TableCell, int, int] | None:
    """Search for a cell whose text contains search_text (case-insensitive).
    Returns (table, cell, row_idx, col_idx) of the first match, or None.
    """
    needle = search_text.strip().lower()
    for table in tables:
        if page_number is not None and table.page_number != page_number:
            continue
        rows = sorted(table.rows, key=lambda r: r.index)
        for row_idx, row in enumerate(rows):
            for col_idx, tc in enumerate(sorted(row.cells, key=lambda c: c.column)):
                if needle in tc.text.strip().lower():
                    return (table, tc, row_idx, col_idx)
    return None


# Maps field_key -> (table_id, row_idx, col_idx) for fields with known static positions.
# Used by excel_populator to look up bbox without re-running extraction.
FIELD_PROVENANCE_SOURCES: dict[str, tuple[str, int, int]] = {
    # Page 1 header (p1_t1)
    "rfq_no": ("p1_t1", 1, 2),
    "customer": ("p1_t1", 2, 2),
    "annual_volume_nos": ("p1_t1", 2, 9),
    "annual_volume_with_rejection": ("p1_t1", 3, 9),
    "final_part_no": ("p1_t1", 3, 2),
    "final_part_rev_no": ("p1_t1", 4, 2),
    "description": ("p1_t1", 5, 2),
    "alloy": ("p1_t1", 6, 2),
    "machined_part_weight_kg": ("p1_t1", 4, 9),
    "casting_weight_kg": ("p1_t1", 5, 9),
    "lbh_length_mm": ("p1_t1", 6, 9),
    "lbh_breadth_mm": ("p1_t1", 6, 9),
    "lbh_height_mm": ("p1_t1", 6, 9),
    "pkg_lbh_length_mm": ("p1_t1", 6, 9),
    "pkg_lbh_breadth_mm": ("p1_t1", 6, 9),
    "pkg_lbh_height_mm": ("p1_t1", 6, 9),
    # Page 1 casting cell details (p1_t1)
    "sand_core_weight_kg": ("p1_t1", 13, 10),
    "casting_man_power": ("p1_t1", 14, 10),
    "casting_floor_space_sq_m": ("p1_t1", 15, 10),
    "surface_coating_involved": ("p1_t1", 19, 10),
    # Page 1 die details (p1_t1)
    "no_of_dies": ("p1_t1", 53, 3),
    "die_amount_per_cell_rs_lac": ("p1_t1", 53, 4),
    "die_life_shots": ("p1_t1", 54, 5),
    "core_box_life_shots": ("p1_t1", 55, 5),
    # Page 1 power rating (p1_t1)
    "casting_cell_power_kw_hr": ("p1_t1", 59, 10),
    "melting_furnace_capacity": ("p1_t1", 61, 9),
    "melting_furnace_power_kw_hr": ("p1_t1", 61, 10),
    "heat_treatment_power": ("p1_t1", 62, 10),
    "shot_blasting_power": ("p1_t1", 63, 10),
    # Page 3 machining header (p3_t1)
    "machining_rfq_no": ("p3_t1", 1, 1),
    "machining_customer": ("p3_t1", 2, 1),
    "machining_annual_volume_nos": ("p3_t1", 2, 7),
    "machining_annual_volume_with_rejection": ("p3_t1", 3, 7),
    "machining_final_part_no": ("p3_t1", 3, 1),
    "machining_final_part_rev_no": ("p3_t1", 4, 1),
    "machining_description": ("p3_t1", 5, 1),
    "machining_part_weight_kg": ("p3_t1", 4, 7),
    # Page 5 assembly cycle time details (p5_t1)
    "assembly_cycle_time_min": ("p5_t1", 8, 2),
    "aam_cycle_time_min": ("p5_t1", 8, 3),
    "assembly_output_per_hr": ("p5_t1", 9, 2),
    "aam_output_per_hr": ("p5_t1", 9, 3),
    "assembly_cell_capacity": ("p5_t1", 10, 2),
    "aam_cell_capacity": ("p5_t1", 10, 3),
    "assembly_cell_utilisation": ("p5_t1", 11, 2),
    "aam_cell_utilisation": ("p5_t1", 11, 3),
    "assembly_no_of_cells": ("p5_t1", 12, 2),
    "aam_no_of_cells": ("p5_t1", 12, 3),
    # Page 5 assembly resource requirements (p5_t1)
    "sealant_consumption_ml": ("p5_t1", 25, 3),
    "aam_sealant_consumption_ml": ("p5_t1", 25, 3),
    "assembly_power_kw_hr": ("p5_t1", 26, 3),
    "aam_power_kw_hr": ("p5_t1", 26, 3),
    "assembly_manpower": ("p5_t1", 28, 3),
    "aam_manpower": ("p5_t1", 28, 3),
    "assembly_floor_space_sq_m": ("p5_t1", 29, 3),
    "aam_floor_space_sq_m": ("p5_t1", 29, 3),
    # Page 5 after-assembly machining resource requirements (p5_t1)
    "aam_resource_power_kw_hr": ("p5_t1", 49, 3),
    "aam_resource_power_kw_hr_2": ("p5_t1", 49, 3),
    "aam_resource_manpower": ("p5_t1", 51, 3),
    "aam_resource_manpower_2": ("p5_t1", 51, 3),
    "aam_resource_floor_space": ("p5_t1", 52, 3),
    "aam_resource_floor_space_2": ("p5_t1", 52, 3),
}


def cell(rows: list[list[str]], row: int, column: int) -> str:
    if row < 0 or row >= len(rows):
        return ""
    if column < 0 or column >= len(rows[row]):
        return ""
    return rows[row][column]


def row_value(rows: list[list[str]], label: str, value_column: int = 1) -> str:
    for row in rows:
        if row and one_line(row[0]).lower() == label.lower():
            return row[value_column] if value_column < len(row) else ""
    return ""


def row_text(row: list[str]) -> str:
    return " ".join(one_line(value) for value in row if one_line(value))


def row_has_text(row: list[str], text: str) -> bool:
    return text.lower() in row_text(row).lower()


def find_row_index(rows: list[list[str]], predicate, start: int = 0) -> int | None:
    for index in range(start, len(rows)):
        if predicate(rows[index]):
            return index
    return None


def row_by_label_prefix(rows: list[list[str]], prefix: str, start: int = 0) -> list[str]:
    prefix_lower = prefix.lower()
    for row in rows[start:]:
        if row and one_line(row[0]).lower().startswith(prefix_lower):
            return row
    return []


def has_formula_error(value: str | None) -> bool:
    return one_line(value).upper() in FORMULA_ERROR_VALUES


def has_any_formula_error(row: list[str]) -> bool:
    return any(has_formula_error(value) for value in row)


def clean_section_title(value: str | None) -> str:
    text = one_line(value)
    text = re.sub(r"\s+Capex\s+Operating.*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def parse_numbered_notes(value: str | None) -> list[dict[str, Any]]:
    text = one_line(value)
    if not text:
        return []
    if ":" in text and text.lower().startswith(("assumptions", "notes")):
        text = text.split(":", 1)[1].strip()

    matches = list(re.finditer(r"(?:^|\s)\(?(\d+)\)\s*", text))
    notes: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        note_text = text[start:end].strip()
        if note_text:
            notes.append({"note_no": int(match.group(1)), "text": note_text})
    return notes


def reverse_vertical_label(value: str | None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if "\n" not in text:
        return " ".join(part[::-1] for part in text.split()).strip()
    return " ".join(part[::-1] for part in reversed(text.splitlines())).strip()


class MeridianStructuredExtractionService:
    PAGE_TITLE_SIGNATURES: dict[int, str] = {
        1: "ESTIMATION FOR GRAVITY DIE CASTING",
        3: "ESTIMATION FOR MACHINING",
        4: "PROCESS PLANNING SHEET",
        5: "ESTIMATION FOR ASSEMBLY",
        6: "RFQ REMARKS",
        7: "ESTIMATION FOR PACKING",
    }
    PAGE_TYPES: dict[int, str] = {
        1: "gdc_estimation",
        2: "die_design_feasibility",
        3: "machining_estimation",
        4: "machining_process_planning",
        5: "assembly_estimation",
        6: "rfq_remarks",
        7: "packing_estimation",
    }

    def __init__(self) -> None:
        self._page_resolution_warnings: list[ExtractionWarning] = []

    def build(
        self,
        extraction: DocumentExtraction,
        pdf_path: Path | None = None,
        *,
        include_raw: bool = False,
    ) -> MeridianExtractionResponse:
        raw_text_by_page = self._extract_raw_text(pdf_path) if include_raw and pdf_path and pdf_path.exists() else {}
        page_map = self._resolve_page_map(extraction)
        pages = [
            self._page_1(extraction, raw_text_by_page.get(page_map.get(1), ""), page_map.get(1)),
            self._page_2(extraction, raw_text_by_page.get(page_map.get(2), ""), page_map.get(2)),
            self._page_3(extraction, raw_text_by_page.get(page_map.get(3), ""), page_map.get(3)),
            self._page_4(extraction, raw_text_by_page.get(page_map.get(4), ""), page_map.get(4)),
            self._page_5(extraction, raw_text_by_page.get(page_map.get(5), ""), page_map.get(5)),
            self._page_6(extraction, raw_text_by_page.get(page_map.get(6), ""), page_map.get(6)),
            self._page_7(extraction, raw_text_by_page.get(page_map.get(7), ""), page_map.get(7)),
        ]
        pages = [self._apply_raw_policy(page, include_raw=include_raw) for page in pages]
        missing_page_warnings = [
            warning(
                "meridian_page_not_found",
                f"{self.PAGE_TYPES[logical_page]} page not found in the uploaded PDF.",
                logical_page,
                {"logical_page": logical_page, "page_type": self.PAGE_TYPES[logical_page]},
            )
            for logical_page in range(1, 8)
            if logical_page not in page_map
        ]
        warnings = [
            *self._page_resolution_warnings,
            *missing_page_warnings,
            *[warning for page in pages for warning in page.warnings],
        ]
        return MeridianExtractionResponse(
            document_id=extraction.document_id,
            filename=extraction.filename,
            page_count=extraction.page_count,
            pages=pages,
            raw_tables=extraction.tables if include_raw else [],
            warnings=[*extraction.warnings, *warnings],
        )

    def _resolve_page_map(self, extraction: DocumentExtraction) -> dict[int, int]:
        self._page_resolution_warnings = []
        page_map: dict[int, int] = {}

        titles_by_physical_page: dict[int, list[str]] = {}
        for table in extraction.tables:
            if not table.title:
                continue
            titles_by_physical_page.setdefault(table.page_number, []).append(table.title.upper())

        for physical_page in range(1, extraction.page_count + 1):
            titles = titles_by_physical_page.get(physical_page, [])
            for logical_page, signature in self.PAGE_TITLE_SIGNATURES.items():
                if not any(signature in title for title in titles):
                    continue
                if logical_page in page_map:
                    self._page_resolution_warnings.append(
                        warning(
                            "duplicate_meridian_page_signature",
                            f"Duplicate Meridian page signature matched logical page {logical_page}; first physical page was kept.",
                            logical_page,
                            {
                                "logical_page": logical_page,
                                "kept_physical_page": page_map[logical_page],
                                "ignored_physical_page": physical_page,
                                "signature": signature,
                            },
                        )
                    )
                    continue
                page_map[logical_page] = physical_page

        assigned_physical_pages = set(page_map.values())
        unassigned_physical_pages = [
            page_number
            for page_number in range(1, extraction.page_count + 1)
            if page_number not in assigned_physical_pages
        ]
        if 2 not in page_map and len(unassigned_physical_pages) == 1:
            page_map[2] = unassigned_physical_pages[0]

        return page_map

    def _apply_raw_policy(self, page: MeridianStructuredPage, *, include_raw: bool) -> MeridianStructuredPage:
        source_refs = [
            {
                "table_id": table.table_id,
                "page_number": table.page_number,
                "title": table.title,
            }
            for table in page.raw_tables
        ]
        return page.model_copy(
            update={
                "source_refs": source_refs,
                "raw_tables": page.raw_tables if include_raw else [],
                "raw_text": page.raw_text if include_raw else "",
            }
        )

    def _extract_raw_text(self, pdf_path: Path) -> dict[int, str]:
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return {}
        try:
            return {index + 1: doc.load_page(index).get_text("text").strip() for index in range(doc.page_count)}
        finally:
            doc.close()

    def _table(self, extraction: DocumentExtraction, table_id: str) -> ExtractedTable | None:
        return next((table for table in extraction.tables if table.table_id == table_id), None)

    def _page_tables(self, extraction: DocumentExtraction, page_number: int | None) -> list[ExtractedTable]:
        if page_number is None:
            return []
        return [table for table in extraction.tables if table.page_number == page_number]

    def _physical_table(self, extraction: DocumentExtraction, physical_page: int | None, suffix: int) -> ExtractedTable | None:
        if physical_page is None:
            return None
        return self._table(extraction, f"p{physical_page}_t{suffix}")

    def _page_1(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        table = self._physical_table(extraction, physical_page, 1)
        rows = matrix(table)
        cells = matrix_cells(table)
        tid = table.table_id if table else "p1_t1"
        page_warnings: list[ExtractionWarning] = []

        header = {
            "rfq_no": cell(rows, 1, 2),
            "date": parse_date(cell(rows, 1, 9)),
            "customer": cell(rows, 2, 2),
            "annual_volume_nos": parse_int(cell(rows, 2, 9)),
            "annual_volume_including_rejection_nos": parse_int(cell(rows, 3, 9)),
            "final_part_no": cell(rows, 3, 2),
            "final_part_rev_no": cell(rows, 4, 2),
            "description": cell(rows, 5, 2),
            "alloy": cell(rows, 6, 2),
            "alternate_alloy_proposed_by_scl": cell(rows, 7, 2),
            "machined_part_weight_kg": parse_float(cell(rows, 4, 9)),
            "casting_weight_kg": parse_float(cell(rows, 5, 9)),
            "lbh_mm": parse_lbh(cell(rows, 6, 9)),
            "takt_time_min": parse_float(cell(rows, 7, 9)),
        }

        output_machine_details = []
        for index in range(9, min(20, len(rows))):
            row = rows[index]
            raw_operation = clean_text(row[0] if row else "")
            value_row = row
            value_index = index
            if raw_operation.startswith("Output/"):
                parts = [part.strip() for part in raw_operation.splitlines() if part.strip()]
                operation = parts[-1] if len(parts) > 1 else ""
                if index + 1 < len(rows):
                    value_row = rows[index + 1]
                    value_index = index + 1
            else:
                operation = one_line(raw_operation)
            if not operation:
                continue
            output_machine_details.append(
                {
                    "operation": operation,
                    "no_of_cavities_or_loading": parse_int(value_row[3] if len(value_row) > 3 else ""),
                    "cycle_time_min": parse_float(value_row[4] if len(value_row) > 4 else ""),
                    "output_per_hr": parse_int(value_row[5] if len(value_row) > 5 else ""),
                    "_sources": {
                        "no_of_cavities_or_loading": src(tid, cell_at(cells, value_index, 3)),
                        "cycle_time_min": src(tid, cell_at(cells, value_index, 4)),
                        "output_per_hr": src(tid, cell_at(cells, value_index, 5)),
                    },
                }
            )

        casting_cell_details = {
            "casting_category": one_line(cell(rows, 11, 10)),
            "no_of_casting_cells_planned": parse_int(cell(rows, 12, 10)),
            "weight_of_sand_core_per_part_kg": parse_float(cell(rows, 13, 10)),
            "man_power_per_shift_per_cell": parse_float(cell(rows, 14, 10)),
            "floor_space_per_cell_sq_m": parse_float(cell(rows, 15, 10)),
            "shot_blasting_type": " ".join(part for part in [one_line(cell(rows, 17, 10)), one_line(cell(rows, 18, 10))] if part),
            "surface_coating_involved": cell(rows, 19, 10),
            "_sources": {
                "shot_blasting_type": src(tid, cell_at(cells, 17, 10)),
            },
        }

        capital_investments = self._page_1_capital(rows, cells, tid)
        operating_costs = self._page_1_operating(rows, cells, tid)
        die_details = self._page_1_die_details(rows, operating_costs)
        testing_cost_details = self._page_1_testing(rows, cells, tid)
        power_rating_details = self._page_1_power(rows)
        approval = {
            "prepared_by": "EA / KVG",
            "approved_by": "JR",
            "validity_note": "This estimation is valid for 90 days only",
            "format_no": "F/PED-EST/03",
            "revision_no": "01",
            "revision_date": "2014-10-08",
            "classification": "Confidential",
        }

        page_warnings.append(
            warning(
                "complex_gdc_table_normalized",
                "Page 1 is a large multi-section table; grouped capital and operating costs are normalized from visual subheadings.",
                1,
            )
        )

        return MeridianStructuredPage(
            page_number=1,
            physical_page_number=physical_page,
            page_type="gdc_estimation",
            title="SCL-PED RFQ ESTIMATION FOR GRAVITY DIE CASTING (GDC)",
            header=header,
            output_machine_details=output_machine_details,
            casting_cell_details=casting_cell_details,
            capital_investments=capital_investments,
            capital_investments_summary={
                "total_investment_rs_lac": self._page_1_capital_total(rows),
            },
            operating_costs=operating_costs,
            die_details=die_details,
            testing_cost_details=testing_cost_details,
            power_rating_details=power_rating_details,
            assumptions_notes=self._page_1_assumptions(rows),
            approval=approval,
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _page_1_capital(
        self,
        rows: list[list[str]],
        cells: list[list[TableCell | None]] | None = None,
        table_id: str = "p1_t1",
    ) -> list[dict[str, Any]]:
        cells = cells or []
        groups: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for index in range(21, min(54, len(rows))):
            row = rows[index]
            label = reverse_vertical_label(row[0] if row else "")
            description = one_line(row[1] if len(row) > 1 else "")
            if description == "Band saw machine":
                current = {"category": "Post casting", "items": []}
                groups.append(current)
            elif label:
                current = {"category": label, "items": []}
                groups.append(current)
            if current is None:
                continue
            if not description or description.lower().startswith("total investment"):
                continue
            current["items"].append(
                {
                    "description": description,
                    "utilisation_percent": parse_percent(row[2] if len(row) > 2 else ""),
                    "units": parse_int(row[3] if len(row) > 3 else ""),
                    "amount_per_cell_rs_lac": parse_float(row[4] if len(row) > 4 else ""),
                    "total_cost_rs_lac": parse_float(row[5] if len(row) > 5 else ""),
                    "_sources": {
                        "description": src(table_id, cell_at(cells, index, 1)),
                        "utilisation_percent": src(table_id, cell_at(cells, index, 2)),
                        "units": src(table_id, cell_at(cells, index, 3)),
                        "amount_per_cell_rs_lac": src(table_id, cell_at(cells, index, 4)),
                        "total_cost_rs_lac": src(table_id, cell_at(cells, index, 5)),
                    },
                }
            )
        return groups

    def _page_1_capital_total(self, rows: list[list[str]]) -> float | None:
        for row in rows:
            if len(row) > 5 and one_line(row[1]).lower().startswith("total investment"):
                return parse_float(row[5])
        return None

    def _page_1_assumptions(self, rows: list[list[str]]) -> list[dict[str, Any]]:
        assumption_row = next((row for row in rows if row and one_line(row[0]).lower().startswith("assumptions/ notes")), [])
        return parse_numbered_notes(assumption_row[0] if assumption_row else "")

    def _page_1_operating(
        self,
        rows: list[list[str]],
        cells: list[list[TableCell | None]] | None = None,
        table_id: str = "p1_t1",
    ) -> list[dict[str, Any]]:
        cells = cells or []
        groups: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for index in range(21, min(58, len(rows))):
            row = rows[index]
            label = reverse_vertical_label(row[7] if len(row) > 7 else "")
            if label:
                current = {"category": label, "items": []}
                groups.append(current)
            if current is None:
                continue
            description = one_line(row[8] if len(row) > 8 else "")
            if not description or description.lower().startswith("power rating"):
                continue
            current["items"].append(
                {
                    "description": description,
                    "amount_rs_lac": parse_float(row[10] if len(row) > 10 else ""),
                    "_sources": {
                        "description": src(table_id, cell_at(cells, index, 8)),
                        "amount_rs_lac": src(table_id, cell_at(cells, index, 10)),
                    },
                }
            )
        return groups

    def _page_1_die_details(self, rows: list[list[str]], operating_costs: list[dict[str, Any]]) -> dict[str, Any]:
        del operating_costs
        die_operating = []
        for index in range(53, 58):
            description = one_line(cell(rows, index, 8))
            if description and not description.lower().startswith("total investment"):
                die_operating.append(
                    {
                        "description": description,
                        "amount_rs_lac": parse_float(cell(rows, index, 10)),
                    }
                )
        return {
            "capital_items": [
                {
                    "description": one_line(cell(rows, 53, 1)),
                    "no_of_dies": parse_int(cell(rows, 53, 3)),
                    "amount_per_cell_rs_lac": parse_float(cell(rows, 53, 4)),
                    "total_cost_rs_lac": parse_float(cell(rows, 53, 5)),
                }
            ],
            "life": {
                "die_life_shots": parse_int(cell(rows, 54, 5)),
                "core_box_life_shots": parse_int(cell(rows, 55, 5)),
            },
            "operating_items": die_operating,
            "operating_total_rs_lac": parse_float(cell(rows, 57, 10)),
        }

    def _page_1_testing(
        self,
        rows: list[list[str]],
        cells: list[list[TableCell | None]] | None = None,
        table_id: str = "p1_t1",
    ) -> dict[str, Any]:
        cells = cells or []
        values: dict[str, Any] = {
            "chemical_testing_cost_per_part_rs": None,
            "x_ray_testing_cost_per_part_rs": None,
            "tensile_testing_cost_per_part_rs": None,
            "microstructure_testing_cost_per_part_rs": None,
            "hardness_testing_cost_per_part_rs": None,
            "inspection_3d_cost_per_part_rs": None,
            "porosity_testing_cost_per_part_rs": None,
            "others_cost_per_part_rs": None,
            "total_testing_cost_per_part_rs": None,
            "_sources": {},
        }
        mapping = {
            "Chemical Testing cost/ part": "chemical_testing_cost_per_part_rs",
            "X Ray Testing cost / part": "x_ray_testing_cost_per_part_rs",
            "Tensile Testing cost / part": "tensile_testing_cost_per_part_rs",
            "Microstructure Testing cost / part": "microstructure_testing_cost_per_part_rs",
            "Hardness Testing cost / part": "hardness_testing_cost_per_part_rs",
            "3D Inspection cost / part": "inspection_3d_cost_per_part_rs",
            "Porosity Testing cost / part": "porosity_testing_cost_per_part_rs",
            "Others (if any)": "others_cost_per_part_rs",
            "Total Testing Cost/ Part": "total_testing_cost_per_part_rs",
        }
        for index in range(56, min(66, len(rows))):
            row = rows[index]
            key = mapping.get(one_line(row[1] if len(row) > 1 else ""))
            if key:
                values[key] = parse_float(row[5] if len(row) > 5 else "")
                values["_sources"][key] = src(table_id, cell_at(cells, index, 5))
        return values

    def _page_1_power(self, rows: list[list[str]]) -> dict[str, Any]:
        return {
            "casting_cell_kw_hr": parse_float(cell(rows, 59, 10)),
            "melting_furnace_capacity": one_line(cell(rows, 61, 9)),
            "melting_furnace_kw_hr": parse_float(cell(rows, 61, 10)),
            "heat_treatment": one_line(cell(rows, 62, 10)),
            "shot_blasting": one_line(cell(rows, 63, 10)),
        }

    def _page_2(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        return MeridianStructuredPage(
            page_number=2,
            physical_page_number=physical_page,
            page_type="die_design_feasibility",
            title="CostEstimation - Die Design",
            header={},
            source_type="image_only",
            ocr_required=True,
            implementation_status="deferred",
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=[
                warning(
                    "image_only_page_skipped",
                    "Page 2 appears to be image-only and requires OCR/image-table extraction, which is out of scope for the current implementation.",
                    2,
                )
            ],
        )

    def _page_3(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        main = self._physical_table(extraction, physical_page, 1)
        rows = matrix(main)
        main_cells = matrix_cells(main)
        main_tid = main.table_id if main else "p3_t1"
        table_top = self._physical_table(extraction, physical_page, 2)
        table_bottom = self._physical_table(extraction, physical_page, 5)
        table_summary = self._physical_table(extraction, physical_page, 3)
        table_resource = self._physical_table(extraction, physical_page, 4)
        operating_top = matrix(table_top)
        cell_summary_rows = matrix(table_summary)
        summary_cells = matrix_cells(table_summary)
        summary_tid = table_summary.table_id if table_summary else "p3_t3"
        resource_rows = matrix(table_resource)
        resource_cells = matrix_cells(table_resource)
        resource_tid = table_resource.table_id if table_resource else "p3_t4"
        operating_bottom = matrix(table_bottom)
        page_warnings: list[ExtractionWarning] = []

        operations = self._page_3_operations(rows, page_warnings, main_cells, main_tid)
        capital_row_index = find_row_index(rows, lambda row: row_has_text(row, "Cell Cycle Time:"))
        if capital_row_index is None:
            capital_row_index = 22

        operating_items = []
        for table, mtx in ((table_top, operating_top), (table_bottom, operating_bottom)):
            op_cells = matrix_cells(table)
            op_tid = table.table_id if table else ""
            for idx, row in enumerate(mtx):
                if not row or one_line(row[0]).lower() == "total oerating cost":
                    continue
                operating_items.append(
                    {
                        "description": one_line(row[0]),
                        "amount_rs": parse_int(row[1] if len(row) > 1 else ""),
                        "_sources": {"amount_rs": src(op_tid, cell_at(op_cells, idx, 1))},
                    }
                )
        total_operating_cost = next(
            (parse_int(row[1]) for row in operating_bottom if row and one_line(row[0]).lower() == "total oerating cost"),
            None,
        )

        return MeridianStructuredPage(
            page_number=3,
            physical_page_number=physical_page,
            page_type="machining_estimation",
            title="SCL-PED RFQ Estimation for Machining",
            header={
                "rfq_no": cell(rows, 1, 1),
                "date": parse_date(cell(rows, 1, 7)),
                "customer": cell(rows, 2, 1),
                "annual_volume_nos": parse_int(cell(rows, 2, 7)),
                "annual_volume_including_rejection_nos": parse_int(cell(rows, 3, 7)),
                "final_part_no": cell(rows, 3, 1),
                "final_part_rev_no": cell(rows, 4, 1),
                "description": cell(rows, 5, 1),
                "alloy": cell(rows, 6, 1),
                "machined_part_weight_kg": parse_float(cell(rows, 4, 7)),
                "lbh_mm": parse_lbh(cell(rows, 5, 7)),
                "takt_time_min": parse_float(cell(rows, 6, 7)),
                "casting_category": cell(rows, 7, 1),
            },
            machining_operations=operations,
            capital_summary={
                "cell_cycle_time_min": parse_float(cell(rows, capital_row_index, 3)),
                "total_capital_expenditure_rs": parse_int(cell(rows, capital_row_index, 7)),
            },
            operating_costs=[
                {
                    "category": "machining_operating_cost",
                    "items": operating_items,
                    "total_operating_cost_rs": total_operating_cost,
                }
            ],
            cell_summary={
                "cell_cycle_time_min": parse_float(row_value(cell_summary_rows, "Cell Cycle Time (Min.)")),
                "cell_capacity_nos": parse_int(row_value(cell_summary_rows, "Cell Capacity (Nos.)")),
                "cell_utilisation_percent": parse_percent(row_value(cell_summary_rows, "Cell Utilisation")),
                "no_of_cells": parse_int(row_value(cell_summary_rows, "No. of Cells")),
                "_sources": {
                    "cell_cycle_time_min": labeled_src(cell_summary_rows, summary_cells, summary_tid, "Cell Cycle Time (Min.)"),
                    "cell_capacity_nos": labeled_src(cell_summary_rows, summary_cells, summary_tid, "Cell Capacity (Nos.)"),
                    "cell_utilisation_percent": labeled_src(cell_summary_rows, summary_cells, summary_tid, "Cell Utilisation"),
                    "no_of_cells": labeled_src(cell_summary_rows, summary_cells, summary_tid, "No. of Cells"),
                },
            },
            resource_requirements={
                "power_rating_for_cell_kw_hr": parse_float(row_value(resource_rows, "Power rating for cell (kw/hr)")),
                "man_power_per_shift_per_cell": parse_float(row_value(resource_rows, "Man Power / Shift / Cell")),
                "floor_area_required_per_cell_sq_m": parse_float(row_value(resource_rows, "Floor area required / cell(Sq.M)")),
                "imp_salvaging_percent": parse_percent(row_value(resource_rows, "IMP Salvaging %")),
                "setup_changeover_considered": parse_bool(row_value(resource_rows, "Setup changeover considered (Y/ N)")),
                "no_of_variants_planned_per_cell": parse_int(row_value(resource_rows, "No of variants planned / cell")),
                "_sources": {
                    "power_rating_for_cell_kw_hr": labeled_src(resource_rows, resource_cells, resource_tid, "Power rating for cell (kw/hr)"),
                    "man_power_per_shift_per_cell": labeled_src(resource_rows, resource_cells, resource_tid, "Man Power / Shift / Cell"),
                    "floor_area_required_per_cell_sq_m": labeled_src(resource_rows, resource_cells, resource_tid, "Floor area required / cell(Sq.M)"),
                    "imp_salvaging_percent": labeled_src(resource_rows, resource_cells, resource_tid, "IMP Salvaging %"),
                    "setup_changeover_considered": labeled_src(resource_rows, resource_cells, resource_tid, "Setup changeover considered (Y/ N)"),
                    "no_of_variants_planned_per_cell": labeled_src(resource_rows, resource_cells, resource_tid, "No of variants planned / cell"),
                },
            },
            assumptions_notes=self._page_3_assumptions(rows),
            approval={
                "prepared_by": "EA / KVG",
                "approved_by": "JR",
                "validity_note": "This estimation is valid for 90 days only",
                "format_no": "F/PED-EST/07",
                "revision_no": "01",
                "revision_date": "2014-10-29",
                "classification": "Confidential",
            },
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _page_3_operations(
        self,
        rows: list[list[str]],
        page_warnings: list[ExtractionWarning],
        cells: list[list[TableCell | None]] | None = None,
        table_id: str = "p3_t1",
    ) -> list[dict[str, Any]]:
        cells = cells or []
        header_index = find_row_index(rows, lambda row: row and one_line(row[0]).lower().startswith("opn. no."))
        start = (header_index + 1) if header_index is not None else 9
        operations: list[dict[str, Any]] = []
        for index in range(start, len(rows)):
            row = rows[index]
            if row_has_text(row, "Cell Cycle Time:") or row_has_text(row, "This estimation is valid") or row_has_text(row, "Operating cost"):
                break
            op_raw = one_line(row[0] if row else "")
            description = one_line(row[1] if len(row) > 1 else "")
            if not op_raw and not description and not row_text(row):
                continue
            if has_any_formula_error(row):
                page_warnings.append(
                    warning(
                        "invalid_operation_row",
                        "Formula error token was present in a machining operation row and the row was skipped.",
                        3,
                        {"table_id": "p3_t1", "row_index": index, "row_text": row_text(row)},
                    )
                )
                continue
            operation_no = parse_int(op_raw)
            if operation_no is None:
                if description or op_raw:
                    page_warnings.append(
                        warning(
                            "invalid_operation_row",
                            "Machining operation row could not be normalized because the operation number is missing or invalid.",
                            3,
                            {"table_id": "p3_t1", "row_index": index, "operation_raw": op_raw, "row_text": row_text(row)},
                        )
                    )
                continue
            if not description:
                page_warnings.append(
                    warning(
                        "blank_operation_row",
                        f"Operation {operation_no} has no operation details and was skipped.",
                        3,
                        {"table_id": "p3_t1", "row_index": index, "operation_no": operation_no, "row_text": row_text(row)},
                    )
                )
                continue
            operations.append(
                {
                    "operation_no": operation_no,
                    "description": description,
                    "cycle_time_min": parse_float(row[3] if len(row) > 3 else ""),
                    "machines_per_cell": parse_int(row[4] if len(row) > 4 else ""),
                    "machine_cost_rs": parse_int(row[5] if len(row) > 5 else ""),
                    "no_of_cells": parse_int(row[6] if len(row) > 6 else ""),
                    "amount_rs": parse_int(row[7] if len(row) > 7 else ""),
                    "_sources": {
                        "description": src(table_id, cell_at(cells, index, 1)),
                        "cycle_time_min": src(table_id, cell_at(cells, index, 3)),
                        "machines_per_cell": src(table_id, cell_at(cells, index, 4)),
                        "machine_cost_rs": src(table_id, cell_at(cells, index, 5)),
                        "no_of_cells": src(table_id, cell_at(cells, index, 6)),
                        "amount_rs": src(table_id, cell_at(cells, index, 7)),
                    },
                }
            )
        return operations

    def _page_3_assumptions(self, rows: list[list[str]]) -> list[dict[str, Any]]:
        assumptions_row = next((row for row in rows if row and one_line(row[0]).lower().startswith("assumptions/ notes")), [])
        return parse_numbered_notes(assumptions_row[0] if assumptions_row else "")

    def _page_4(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        rows = matrix(self._physical_table(extraction, physical_page, 1))
        return MeridianStructuredPage(
            page_number=4,
            physical_page_number=physical_page,
            page_type="machining_process_planning",
            title="SCL-PED RFQ Process Planning Sheet",
            header={
                "rfq_no": cell(rows, 1, 1),
                "date": parse_date(cell(rows, 1, 3)),
                "customer": cell(rows, 2, 1),
                "annual_volume_nos": parse_int(cell(rows, 2, 3)),
                "annual_volume_including_rejection_nos": parse_int(cell(rows, 3, 3)),
                "final_part_no": cell(rows, 3, 1),
                "final_part_rev_no": cell(rows, 4, 1),
                "description": cell(rows, 5, 1),
                "alloy": cell(rows, 6, 1),
                "machined_part_weight_kg": parse_float(cell(rows, 4, 3)),
                "lbh_mm": parse_lbh(cell(rows, 5, 3)),
                "takt_time_min": parse_float(cell(rows, 6, 3)),
            },
            input_components=[{"label": "Input component", "image_present": True, "description": None}],
            process_sequences=[
                {
                    "sequence_label": "Machining process sequence",
                    "sequence_code": None,
                    "extraction_status": "vision_layout_deferred",
                    "steps": [],
                    "unassigned_operations": [],
                    "deferred_reason": "Process sequence content is visual/layout-heavy and requires OCR or vision LLM extraction.",
                }
            ],
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=[
                warning("process_sequence_deferred", "Page 4 process sequence requires layout-aware OCR or vision LLM extraction and is deferred in this deterministic pass.", 4),
            ],
        )

    def _process_step(self, step_index: int, label: str, machine_no: int, machine_type: str, setup: str | None, operations: list[str]) -> dict[str, Any]:
        return {
            "step_index": step_index,
            "machine_label": label,
            "machine_no": machine_no,
            "machine_type": machine_type,
            "setup": setup,
            "operations": [
                {"text": operation, "assignment_status": "assigned", "confidence": "medium"}
                for operation in operations
            ],
            "visual_annotations": [],
            "image_present": True,
        }

    def _page_5(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        rows = matrix(self._physical_table(extraction, physical_page, 1))
        page_warnings: list[ExtractionWarning] = []
        lbh_raw = cell(rows, 5, 3)
        lbh = parse_lbh(lbh_raw)
        if one_line(lbh_raw) and any(lbh[dimension] is None for dimension in ("length", "breadth", "height")):
            page_warnings.append(
                warning(
                    "suspicious_lbh_value",
                    f"Page 5 has LBH (mm) value {one_line(lbh_raw)!r}, which does not match a length x breadth x height format.",
                    5,
                    {"value": one_line(lbh_raw)},
                )
            )
        after_assembly_raw = cell(rows, 31, 3)
        after_assembly_bool = parse_bool(after_assembly_raw)
        if one_line(after_assembly_raw) and one_line(after_assembly_raw).lower() not in {"yes", "y", "no", "n", "true", "false"}:
            page_warnings.append(
                warning(
                    "non_boolean_after_assembly_flag",
                    f"After assembly machining involved field contains {one_line(after_assembly_raw)!r}; normalized as {after_assembly_bool}.",
                    5,
                    {"value": one_line(after_assembly_raw), "normalized": after_assembly_bool},
                )
            )

        return MeridianStructuredPage(
            page_number=5,
            physical_page_number=physical_page,
            page_type="assembly_estimation",
            title="SCL-PED RFQ ESTIMATION FOR ASSEMBLY",
            header={
                "rfq_no": cell(rows, 1, 1),
                "date": parse_date(cell(rows, 1, 3)),
                "customer": cell(rows, 2, 1),
                "annual_volume_nos": parse_int(cell(rows, 2, 3)),
                "annual_volume_including_rejection_nos": parse_int(cell(rows, 3, 3)),
                "final_part_no": cell(rows, 3, 1),
                "final_part_rev_no": cell(rows, 4, 1),
                "description": cell(rows, 5, 1),
                "alloy": cell(rows, 6, 1),
                "machined_part_weight_kg": parse_float(cell(rows, 4, 3)),
                "lbh_mm": lbh,
                "takt_time_min": parse_float(cell(rows, 6, 3)),
            },
            cycle_time_details={
                "assembly": {
                    "cycle_time_min": parse_float(cell(rows, 8, 2)),
                    "output_per_hour_nos": parse_int(cell(rows, 9, 2)),
                    "cell_capacity_nos": parse_int(cell(rows, 10, 2)),
                    "cell_utilisation_percent": parse_percent(cell(rows, 11, 2)),
                    "no_of_cells_required": parse_int(cell(rows, 12, 2)),
                },
                "after_assembly_machining": {
                    "cycle_time_min": parse_float(cell(rows, 8, 3)),
                    "output_per_hour_nos": parse_int(cell(rows, 9, 3)),
                    "cell_capacity_nos": parse_int(cell(rows, 10, 3)),
                    "cell_utilisation_percent": parse_percent(cell(rows, 11, 3)),
                    "no_of_cells_required": parse_int(cell(rows, 12, 3)),
                },
            },
            assembly_investments=self._page_5_assembly_investments(rows),
            assembly_resource_requirements={
                "sealant_consumption_per_part_ml": parse_float(cell(rows, 25, 3)),
                "sealant_type": self._page_5_sealant_type(rows),
                "power_rating_kw_hr": parse_float(cell(rows, 26, 3)),
                "feasible_to_use_machining_operator_for_assembly": parse_bool(cell(rows, 27, 3)),
                "manpower_per_shift_per_cell": parse_float(cell(rows, 28, 3)),
                "floor_space_required_sq_m_per_cell": parse_float(cell(rows, 29, 3)),
            },
            after_assembly_machining=self._page_5_after_assembly(rows),
            part_references={"machined_part_no_rev": None, "casting_part_no_rev": None, "child_part_nos": []},
            approval={
                "prepared_by": "EA / KVG",
                "approved_by": "JR",
                "validity_note": "This estimation is valid for 90 days only",
                "format_no": "F/PED-EST/05",
                "revision_no": "01",
                "revision_date": "2014-10-29",
                "classification": "Confidential",
                "extraction_status": "fallback_defaults",
            },
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _page_5_assembly_investments(self, rows: list[list[str]]) -> dict[str, Any]:
        section_index = find_row_index(rows, lambda row: row and "before afm machining assembly" in one_line(row[0]).lower())
        if section_index is None:
            section_index = 13
        total_index = find_row_index(rows, lambda row: row and one_line(row[0]).lower().startswith("total assembly investment"), section_index + 1)
        item_rows = rows[section_index + 1 : total_index] if total_index is not None else rows[section_index + 1 :]
        items = []
        for row in item_rows:
            description = one_line(row[0] if row else "")
            if not description or description.lower() in {"capex", "operating"}:
                continue
            items.append(
                {
                    "description": description,
                    "capex_rs": parse_float(row[2] if len(row) > 2 else ""),
                    "operating_rs": parse_float(row[3] if len(row) > 3 else ""),
                }
            )
        total_row = row_by_label_prefix(rows, "Total Assembly Investment", section_index + 1)
        all_cells_row = row_by_label_prefix(rows, "Total Assembly Investment for all cells", section_index + 1)
        return {
            "section_title": clean_section_title(cell(rows, section_index, 0)),
            "items": items,
            "total_assembly_investment": {
                "capex_rs": parse_float(total_row[2] if len(total_row) > 2 else ""),
                "operating_rs": parse_float(total_row[3] if len(total_row) > 3 else ""),
            },
            "total_assembly_investment_for_all_cells": {
                "capex_rs": parse_float(all_cells_row[2] if len(all_cells_row) > 2 else ""),
                "operating_rs": parse_float(all_cells_row[3] if len(all_cells_row) > 3 else ""),
            },
        }

    def _page_5_after_assembly(self, rows: list[list[str]]) -> dict[str, Any]:
        involved_row = row_by_label_prefix(rows, "Is after assembly machining involved?")
        section_index = find_row_index(rows, lambda row: row and one_line(row[0]).lower() == "before afm machining")
        if section_index is None:
            section_index = 32
        total_index = find_row_index(rows, lambda row: row and one_line(row[0]).lower().startswith("total after assembly machining investment"), section_index + 1)
        item_rows = rows[section_index + 1 : total_index] if total_index is not None else rows[section_index + 1 :]
        items = []
        for row in item_rows:
            description = one_line(row[0] if row else "")
            if not description:
                continue
            items.append(
                {
                    "description": description,
                    "capex_rs": parse_float(row[2] if len(row) > 2 else ""),
                    "operating_rs": parse_float(row[3] if len(row) > 3 else ""),
                    "cycle_time_min": parse_float(row[4] if len(row) > 4 else ""),
                }
            )
        total_row = row_by_label_prefix(rows, "Total after assembly machining Investment", section_index + 1)
        all_cells_row = row_by_label_prefix(rows, "Total after assembly machining Investment for all cells", section_index + 1)
        total_assy_row = row_by_label_prefix(rows, "TOTAL ASSY INVESTMENTS", section_index + 1)
        return {
            "involved": parse_bool(involved_row[3] if len(involved_row) > 3 else ""),
            "involved_raw": involved_row[3] if len(involved_row) > 3 else "",
            "section_title": clean_section_title(cell(rows, section_index, 0)),
            "items": items,
            "total_after_assembly_machining_investment": {
                "capex_rs": parse_float(total_row[2] if len(total_row) > 2 else ""),
                "operating_rs": parse_float(total_row[3] if len(total_row) > 3 else ""),
            },
            "total_after_assembly_machining_investment_for_all_cells": {
                "capex_rs": parse_float(all_cells_row[2] if len(all_cells_row) > 2 else ""),
                "operating_rs": parse_float(all_cells_row[3] if len(all_cells_row) > 3 else ""),
            },
            "total_assy_investments": {
                "capex_rs": parse_float(total_assy_row[2] if len(total_assy_row) > 2 else ""),
                "operating_rs": parse_float(total_assy_row[3] if len(total_assy_row) > 3 else ""),
            },
            "resource_requirements": {
                "power_rating_kw_hr": parse_float(cell(rows, 49, 3)),
                "feasible_to_use_machining_cell_operator": parse_bool(cell(rows, 50, 3)),
                "manpower_per_shift_per_cell": parse_float(cell(rows, 51, 3)),
                "floor_space_required_sq_m_per_cell": parse_float(cell(rows, 52, 3)),
            },
        }

    def _page_5_sealant_type(self, rows: list[list[str]]) -> str | None:
        row = row_by_label_prefix(rows, "Sealant consumption/ part")
        label = one_line(row[0] if row else "")
        match = re.search(r"\(ml\)\s*(.+)$", label, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _page_6(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        rows = matrix(self._physical_table(extraction, physical_page, 1))
        casting_rows = matrix(self._physical_table(extraction, physical_page, 2))
        machining_rows = matrix(self._physical_table(extraction, physical_page, 3))
        has_email_image = self._page_has_image(extraction, physical_page)
        remarks_sections, duplicate_count = self._page_6_remarks_sections(rows, casting_rows, machining_rows, has_email_image)
        email_evidence = (
            [
                {
                    "evidence_id": "page6_email_1",
                    "source_type": "embedded_image",
                    "extraction_status": "vision_llm_deferred",
                    "linked_remark_sections": ["casting"],
                    "subject": None,
                    "from": None,
                    "to": [],
                    "cc": [],
                    "sent_at": None,
                    "body_text": None,
                    "extracted_points": [],
                    "raw_image_ref": {"page_number": 6, "image_index": 1},
                }
            ]
            if has_email_image
            else []
        )
        page_warnings: list[ExtractionWarning] = []
        if has_email_image:
            page_warnings.append(
                warning(
                    "email_screenshot_deferred",
                    "Page 6 contains embedded image evidence that requires vision LLM extraction.",
                    6,
                    {"image_ref": {"page_number": 6, "image_index": 1}},
                )
            )
        if duplicate_count:
            page_warnings.append(
                warning(
                    "duplicate_machining_remarks",
                    "Duplicate machining remarks were detected across extracted tables/text and deduplicated.",
                    6,
                    {"duplicate_count": duplicate_count},
                )
            )

        return MeridianStructuredPage(
            page_number=6,
            physical_page_number=physical_page,
            page_type="rfq_remarks",
            title="SCL-PED RFQ REMARKS",
            header={
                "rfq_no": cell(rows, 1, 1),
                "date": parse_date(cell(rows, 1, 3)),
                "customer": cell(rows, 2, 1),
                "annual_volume_nos": parse_int(cell(rows, 2, 3)),
                "annual_volume_including_rejection_nos": parse_int(cell(rows, 3, 3)),
                "final_part_no": cell(rows, 3, 1),
                "final_part_rev_no": cell(rows, 4, 1),
                "description": cell(rows, 5, 1),
                "alloy": cell(rows, 6, 1),
                "alternate_alloy_proposed_by_scl": cell(rows, 7, 1),
                "machined_part_weight_kg": parse_float(cell(rows, 4, 3)),
                "casting_weight_kg": parse_float(cell(rows, 5, 3)),
                "lbh_mm": parse_lbh(cell(rows, 6, 3)),
            },
            remarks_sections=remarks_sections,
            email_evidence=email_evidence,
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _page_has_image(self, extraction: DocumentExtraction, page_number: int | None) -> bool:
        if page_number is None:
            return False
        page = next((page for page in extraction.pages if page.page_number == page_number), None)
        return bool(page and page.image_count > 0)

    def _page_6_remarks_sections(
        self,
        main_rows: list[list[str]],
        casting_rows: list[list[str]],
        machining_rows: list[list[str]],
        has_email_image: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        sections: dict[str, dict[str, Any]] = {}
        duplicate_count = 0

        def ensure_section(title: str) -> dict[str, Any]:
            section_type = self._remark_section_type(title)
            if section_type not in sections:
                sections[section_type] = {"section_type": section_type, "title": title, "items": []}
            return sections[section_type]

        def add_items(section: dict[str, Any], new_items: list[dict[str, Any]]) -> None:
            nonlocal duplicate_count
            seen = {one_line(item["text"]).lower() for item in section["items"]}
            for item in new_items:
                key = one_line(item["text"]).lower()
                if key in seen:
                    duplicate_count += 1
                    continue
                section["items"].append(item)
                seen.add(key)

        for row in main_rows:
            lines = [line.strip() for line in clean_text(row[0] if row else "").splitlines() if line.strip()]
            if not lines:
                continue
            heading_match = re.match(r"^(.+?\s+Remarks):$", lines[0], flags=re.IGNORECASE)
            if not heading_match:
                continue
            section = ensure_section(heading_match.group(1))
            add_items(section, self._page_6_remark_items(lines[1:], has_email_image=has_email_image))

        casting_section = ensure_section("Casting Remarks")
        add_items(casting_section, self._page_6_remark_items(self._table_lines(casting_rows), has_email_image=has_email_image))

        machining_section = ensure_section("Machining Remarks")
        add_items(machining_section, self._page_6_remark_items(self._table_lines(machining_rows), has_email_image=has_email_image))

        if "assembly" not in sections:
            ensure_section("Assembly Remarks")

        return list(sections.values()), duplicate_count

    def _page_6_remark_items(self, lines: list[str], *, has_email_image: bool, force_email_refs: bool = False) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.lower().startswith("factors into our pricing"):
                continue
            number_match = re.match(r"^(\d+)\.\s*(.+)$", stripped)
            refs = self._page_6_evidence_refs(stripped, has_email_image=has_email_image, force_email_refs=force_email_refs or bool(number_match))
            if number_match:
                items.append(
                    {
                        "number": int(number_match.group(1)),
                        "text": number_match.group(2),
                        "item_type": "numbered_remark",
                        "source": "pdf_text",
                        "evidence_refs": refs,
                    }
                )
            else:
                items.append(
                    {
                        "text": stripped,
                        "item_type": "remark",
                        "source": "pdf_text",
                        "evidence_refs": refs,
                    }
                )
        return items

    def _page_6_evidence_refs(self, text: str, *, has_email_image: bool, force_email_refs: bool = False) -> list[str]:
        if not has_email_image:
            return []
        lowered = text.lower()
        if force_email_refs or "email" in lowered or "afm process" in lowered:
            return ["page6_email_1"]
        return []

    def _table_lines(self, rows: list[list[str]]) -> list[str]:
        lines: list[str] = []
        for row in rows:
            text = clean_text(row[0] if row else "")
            if not text:
                continue
            lines.extend(line.strip() for line in text.splitlines() if line.strip())
        return lines

    def _remark_section_type(self, title: str) -> str:
        text = re.sub(r"\s+remarks?$", "", title.strip(), flags=re.IGNORECASE)
        key = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        return key or "other"

    def _page_7(self, extraction: DocumentExtraction, raw_text: str, physical_page: int | None) -> MeridianStructuredPage:
        rows = matrix(self._physical_table(extraction, physical_page, 1))
        page_warnings: list[ExtractionWarning] = []
        section_title = one_line(cell(rows, 7, 0))
        if "\n" in clean_text(cell(rows, 1, 2)) or "annual volume" in one_line(cell(rows, 1, 2)).lower():
            page_warnings.append(
                warning(
                    "messy_header_extraction",
                    "Page 7 header labels were merged into one extracted table cell; normalized header values were reconstructed from table/text positions.",
                    7,
                    {"source_value": clean_text(cell(rows, 1, 2))},
                )
            )
        if "qunaity" in section_title.lower():
            page_warnings.append(
                warning(
                    "source_typo_preserved",
                    "Section title contains source spelling 'qunaity'; preserve source title unless explicitly normalized.",
                    7,
                    {"section_title": section_title},
                )
            )
        arrangements = self._page_7_arrangements(rows, page_warnings)
        selected_components = parse_int(row_value(rows, "No. of components per box", 3))
        selected_arrangement_no = self._page_7_selected_arrangement_no(arrangements, selected_components)
        if selected_components is not None and selected_arrangement_no is None:
            page_warnings.append(
                warning(
                    "selected_arrangement_not_inferred",
                    "Selected number of components per box is present, but selected arrangement number is not uniquely inferable.",
                    7,
                    {"selected_no_of_components_per_box": selected_components},
                )
            )
        return MeridianStructuredPage(
            page_number=7,
            physical_page_number=physical_page,
            page_type="packing_estimation",
            title="SCL-PED RFQ ESTIMATION FOR PACKING 334",
            header={
                "rfq_no": cell(rows, 1, 1),
                "date": parse_date(cell(rows, 1, 4)),
                "customer": cell(rows, 2, 1),
                "annual_volume_nos": parse_int(cell(rows, 2, 4)),
                "annual_volume_including_rejection_nos": parse_int(cell(rows, 3, 4)),
                "final_part_no": cell(rows, 3, 1),
                "final_part_rev_no": cell(rows, 4, 1),
                "description": cell(rows, 5, 1),
                "alloy": cell(rows, 6, 1),
                "machined_part_weight_kg": parse_float(cell(rows, 4, 4)),
                "lbh_mm": parse_lbh(cell(rows, 5, 4)),
            },
            packing_box_quantity_working={
                "section_title": section_title,
                "component_image_present": True,
                "part_size_mm": self._dimensions_row(rows, "Part size"),
                "packing_box_size_mm": self._dimensions_row(rows, "Packing box size"),
                "allowances_mm": self._dimensions_row(rows, "Allowances"),
                "arrangements": arrangements,
                "selected_no_of_components_per_box": selected_components,
                "selected_arrangement_no": selected_arrangement_no,
                "free_text_rows": self._page_7_free_text_rows(rows),
            },
            raw_tables=self._page_tables(extraction, physical_page),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _dimensions_row(self, rows: list[list[str]], label: str) -> dict[str, int | None]:
        for row in rows:
            if row and one_line(row[0]).lower() == label.lower():
                return {
                    "length": parse_int(row[3] if len(row) > 3 else ""),
                    "breadth": parse_int(row[4] if len(row) > 4 else ""),
                    "height": parse_int(row[5] if len(row) > 5 else ""),
                }
        return {"length": None, "breadth": None, "height": None}

    def _page_7_arrangements(self, rows: list[list[str]], page_warnings: list[ExtractionWarning] | None = None) -> list[dict[str, Any]]:
        arrangements = []
        for index, row in enumerate(rows):
            label = one_line(row[0] if row else "")
            match = re.fullmatch(r"Arrangement\s+(\d+)", label)
            if not match:
                continue
            components_row = self._page_7_nearby_components_row(rows, index)
            no_of_components = parse_int(components_row[3] if len(components_row) > 3 else "")
            if page_warnings is not None and no_of_components is None:
                page_warnings.append(
                    warning(
                        "incomplete_arrangement_row",
                        f"Arrangement {match.group(1)} did not have a nearby parseable component-count row.",
                        7,
                        {"arrangement_no": int(match.group(1)), "row_index": index, "row_text": row_text(row)},
                    )
                )
            arrangements.append(
                {
                    "arrangement_no": int(match.group(1)),
                    "length_count": parse_float(row[3] if len(row) > 3 else ""),
                    "breadth_count": parse_float(row[4] if len(row) > 4 else ""),
                    "height_count": parse_float(row[5] if len(row) > 5 else ""),
                    "no_of_components": no_of_components,
                }
            )
        return arrangements

    def _page_7_nearby_components_row(self, rows: list[list[str]], arrangement_index: int) -> list[str]:
        for row in rows[arrangement_index + 1 : min(arrangement_index + 4, len(rows))]:
            label = one_line(row[0] if row else "").lower()
            if label.startswith("no. of components") and "per box" not in label:
                return row
        return []

    def _page_7_selected_arrangement_no(self, arrangements: list[dict[str, Any]], selected_components: int | None) -> int | None:
        if selected_components is None:
            return None
        matches = [arrangement["arrangement_no"] for arrangement in arrangements if arrangement.get("no_of_components") == selected_components]
        return matches[0] if len(matches) == 1 else None

    def _page_7_free_text_rows(self, rows: list[list[str]]) -> list[dict[str, str]]:
        selected_index = find_row_index(rows, lambda row: row and one_line(row[0]).lower().startswith("no. of components per box"))
        if selected_index is None:
            return []
        free_text_rows: list[dict[str, str]] = []
        for row in rows[selected_index + 1 :]:
            text = one_line(row[0] if row else "")
            if text:
                free_text_rows.append({"text": text, "source": "pdf_text"})
        return free_text_rows
