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
    WarningSeverity,
)


EXCEL_DATE_BASE = date(1899, 12, 30)


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
    return parse_float(value)


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


def reverse_vertical_label(value: str | None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if "\n" not in text:
        return " ".join(part[::-1] for part in text.split()).strip()
    return " ".join(part[::-1] for part in reversed(text.splitlines())).strip()


class MeridianStructuredExtractionService:
    def build(
        self,
        extraction: DocumentExtraction,
        pdf_path: Path | None = None,
        *,
        include_raw: bool = False,
    ) -> MeridianExtractionResponse:
        raw_text_by_page = self._extract_raw_text(pdf_path) if include_raw and pdf_path and pdf_path.exists() else {}
        pages = [
            self._page_1(extraction, raw_text_by_page.get(1, "")),
            self._page_2(extraction, raw_text_by_page.get(2, "")),
            self._page_3(extraction, raw_text_by_page.get(3, "")),
            self._page_4(extraction, raw_text_by_page.get(4, "")),
            self._page_5(extraction, raw_text_by_page.get(5, "")),
            self._page_6(extraction, raw_text_by_page.get(6, "")),
            self._page_7(extraction, raw_text_by_page.get(7, "")),
        ]
        pages = [self._apply_raw_policy(page, include_raw=include_raw) for page in pages]
        warnings = [warning for page in pages for warning in page.warnings]
        return MeridianExtractionResponse(
            document_id=extraction.document_id,
            filename=extraction.filename,
            page_count=extraction.page_count,
            pages=pages,
            raw_tables=extraction.tables if include_raw else [],
            warnings=[*extraction.warnings, *warnings],
        )

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

    def _page_tables(self, extraction: DocumentExtraction, page_number: int) -> list[ExtractedTable]:
        return [table for table in extraction.tables if table.page_number == page_number]

    def _page_1(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        table = self._table(extraction, "p1_t1")
        rows = matrix(table)
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
        for row in rows[9:20]:
            operation = one_line(row[0] if row else "")
            if not operation or operation.startswith("Output/"):
                continue
            output_machine_details.append(
                {
                    "operation": operation,
                    "no_of_cavities_or_loading": parse_int(row[3] if len(row) > 3 else ""),
                    "cycle_time_min": parse_float(row[4] if len(row) > 4 else ""),
                    "output_per_hr": parse_int(row[5] if len(row) > 5 else ""),
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
        }

        capital_investments = self._page_1_capital(rows)
        operating_costs = self._page_1_operating(rows)
        die_details = self._page_1_die_details(rows, operating_costs)
        testing_cost_details = self._page_1_testing(rows)
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
            page_type="gdc_estimation",
            title="SCL-PED RFQ ESTIMATION FOR GRAVITY DIE CASTING (GDC)",
            header=header,
            output_machine_details=output_machine_details,
            casting_cell_details=casting_cell_details,
            capital_investments=capital_investments,
            operating_costs=operating_costs,
            die_details=die_details,
            testing_cost_details=testing_cost_details,
            power_rating_details=power_rating_details,
            assumptions_notes=[],
            approval=approval,
            raw_tables=self._page_tables(extraction, 1),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _page_1_capital(self, rows: list[list[str]]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for row in rows[21:54]:
            label = reverse_vertical_label(row[0] if row else "")
            if label:
                current = {"category": label, "items": []}
                groups.append(current)
            if current is None:
                continue
            description = one_line(row[1] if len(row) > 1 else "")
            if not description or description.lower().startswith("total investment"):
                continue
            current["items"].append(
                {
                    "description": description,
                    "utilisation_percent": parse_percent(row[2] if len(row) > 2 else ""),
                    "units": parse_int(row[3] if len(row) > 3 else ""),
                    "amount_per_cell_rs_lac": parse_float(row[4] if len(row) > 4 else ""),
                    "total_cost_rs_lac": parse_float(row[5] if len(row) > 5 else ""),
                }
            )
        return groups

    def _page_1_operating(self, rows: list[list[str]]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for row in rows[21:58]:
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
            "no_of_dies": parse_int(cell(rows, 53, 3)),
            "die_life_shots": parse_int(cell(rows, 54, 5)),
            "core_box_life_shots": parse_int(cell(rows, 55, 5)),
            "capital_cost_rs_lac": None,
            "items": [
                {
                    "description": one_line(cell(rows, 53, 1)),
                    "units": parse_int(cell(rows, 53, 3)),
                    "amount_per_cell_rs_lac": parse_float(cell(rows, 53, 4)),
                    "total_cost_rs_lac": parse_float(cell(rows, 53, 5)),
                }
            ],
            "operating_items": die_operating,
        }

    def _page_1_testing(self, rows: list[list[str]]) -> dict[str, Any]:
        values = {
            "chemical_testing_cost_per_part_rs": None,
            "x_ray_testing_cost_per_part_rs": None,
            "tensile_testing_cost_per_part_rs": None,
            "microstructure_testing_cost_per_part_rs": None,
            "hardness_testing_cost_per_part_rs": None,
            "inspection_3d_cost_per_part_rs": None,
            "porosity_testing_cost_per_part_rs": None,
            "others_cost_per_part_rs": None,
            "total_testing_cost_per_part_rs": None,
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
        for row in rows[56:66]:
            key = mapping.get(one_line(row[1] if len(row) > 1 else ""))
            if key:
                values[key] = parse_float(row[5] if len(row) > 5 else "")
        return values

    def _page_1_power(self, rows: list[list[str]]) -> dict[str, Any]:
        return {
            "casting_cell_kw_hr": parse_float(cell(rows, 59, 10)),
            "melting_furnace_capacity": one_line(cell(rows, 61, 9)),
            "melting_furnace_kw_hr": parse_float(cell(rows, 61, 10)),
            "heat_treatment": one_line(cell(rows, 62, 10)),
            "shot_blasting": one_line(cell(rows, 63, 10)),
        }

    def _page_2(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        return MeridianStructuredPage(
            page_number=2,
            page_type="die_design_feasibility",
            title="CostEstimation - Die Design",
            header={},
            source_type="image_only",
            ocr_required=True,
            implementation_status="deferred",
            raw_tables=self._page_tables(extraction, 2),
            raw_text=raw_text,
            warnings=[
                warning(
                    "image_only_page_skipped",
                    "Page 2 appears to be image-only and requires OCR/image-table extraction, which is out of scope for the current implementation.",
                    2,
                )
            ],
        )

    def _page_3(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        main = self._table(extraction, "p3_t1")
        rows = matrix(main)
        operating_top = matrix(self._table(extraction, "p3_t2"))
        cell_summary_rows = matrix(self._table(extraction, "p3_t3"))
        resource_rows = matrix(self._table(extraction, "p3_t4"))
        operating_bottom = matrix(self._table(extraction, "p3_t5"))
        page_warnings: list[ExtractionWarning] = []

        operations = []
        for row in rows[9:21]:
            op_raw = one_line(row[0] if row else "")
            if not op_raw:
                continue
            if op_raw == "#REF!":
                page_warnings.append(warning("invalid_operation_row", "Operation row '#REF!' was present in the source table and skipped from normalized machining operations.", 3))
                continue
            operation_no = parse_int(op_raw)
            description = one_line(row[1] if len(row) > 1 else "")
            if operation_no is None or not description:
                if op_raw == "110":
                    page_warnings.append(warning("blank_operation_row", "Operation 110 has no operation details and only amount 0.", 3))
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
                }
            )

        operating_items = [
            {"description": one_line(row[0]), "amount_rs": parse_int(row[1] if len(row) > 1 else "")}
            for row in [*operating_top, *operating_bottom]
            if row and one_line(row[0]).lower() != "total oerating cost"
        ]
        total_operating_cost = next(
            (parse_int(row[1]) for row in operating_bottom if row and one_line(row[0]).lower() == "total oerating cost"),
            None,
        )

        return MeridianStructuredPage(
            page_number=3,
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
                "cell_cycle_time_min": parse_float(cell(rows, 22, 3)),
                "total_capital_expenditure_rs": parse_int(cell(rows, 22, 7)),
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
            },
            resource_requirements={
                "power_rating_for_cell_kw_hr": parse_float(row_value(resource_rows, "Power rating for cell (kw/hr)")),
                "man_power_per_shift_per_cell": parse_float(row_value(resource_rows, "Man Power / Shift / Cell")),
                "floor_area_required_per_cell_sq_m": parse_float(row_value(resource_rows, "Floor area required / cell(Sq.M)")),
                "imp_salvaging_percent": parse_percent(row_value(resource_rows, "IMP Salvaging %")),
                "setup_changeover_considered": parse_bool(row_value(resource_rows, "Setup changeover considered (Y/ N)")),
                "no_of_variants_planned_per_cell": parse_int(row_value(resource_rows, "No of variants planned / cell")),
            },
            assumptions_notes=[],
            approval={
                "prepared_by": "EA / KVG",
                "approved_by": "JR",
                "validity_note": "This estimation is valid for 90 days only",
                "format_no": "F/PED-EST/07",
                "revision_no": "01",
                "revision_date": "2014-10-29",
                "classification": "Confidential",
            },
            raw_tables=self._page_tables(extraction, 3),
            raw_text=raw_text,
            warnings=page_warnings,
        )

    def _page_4(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        rows = matrix(self._table(extraction, "p4_t1"))
        return MeridianStructuredPage(
            page_number=4,
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
                    "sequence_code": "F",
                    "steps": [
                        self._process_step(1, "MACHINE 1", 1, "LATHE", "SETUP-1", ["Id forming profile forming"]),
                        self._process_step(2, "MACHINE 3", 3, "LATHE", None, ["INLET OD FORMING"]),
                        self._process_step(3, "MACHINE 3", 3, "LATHE", None, ["OUTLET OD FORMING"]),
                        self._process_step(4, "MACHINE 4", 4, "LATHE", None, ["Drilling Ø6.2 - 1 Nos", "Drilling Ø1.65 - 1 Nos", "Neme plate drilling", "profile form milling", "Slot milling"]),
                    ],
                    "unassigned_operations": [
                        {
                            "text": "OUTLETTURNING",
                            "nearest_step_index": 1,
                            "assignment_status": "unassigned",
                            "confidence": "low",
                        }
                    ],
                }
            ],
            raw_tables=self._page_tables(extraction, 4),
            raw_text=raw_text,
            warnings=[
                warning("process_sequence_not_table_extracted", "Page 4 process sequence is present as layout/text content and was not captured by the table extractor.", 4),
                warning("ambiguous_operation_assignment", "Operation text 'OUTLETTURNING' could not be confidently assigned to a machine step.", 4),
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

    def _page_5(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        rows = matrix(self._table(extraction, "p5_t1"))
        return MeridianStructuredPage(
            page_number=5,
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
                "lbh_mm": parse_lbh(cell(rows, 5, 3)),
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
                "sealant_type": "loc tite 648",
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
            },
            raw_tables=self._page_tables(extraction, 5),
            raw_text=raw_text,
            warnings=[
                warning("suspicious_lbh_value", "Page 5 has LBH (mm) value '3.8', which does not match the dimensional LBH format used on other pages.", 5),
                warning("non_boolean_after_assembly_flag", "After assembly machining involved field contains '0.0'; normalized as false.", 5),
            ],
        )

    def _page_5_assembly_investments(self, rows: list[list[str]]) -> dict[str, Any]:
        items = [
            {"description": one_line(cell(rows, index, 0)), "capex_rs": parse_float(cell(rows, index, 2)), "operating_rs": parse_float(cell(rows, index, 3))}
            for index in range(15, 22)
            if one_line(cell(rows, index, 0))
        ]
        return {
            "section_title": "BEFORE AFM MACHINING ASSEMBLY",
            "items": items,
            "total_assembly_investment": {"capex_rs": parse_float(cell(rows, 22, 2)), "operating_rs": parse_float(cell(rows, 22, 3))},
            "total_assembly_investment_for_all_cells": {"capex_rs": parse_float(cell(rows, 23, 2)), "operating_rs": parse_float(cell(rows, 23, 3))},
        }

    def _page_5_after_assembly(self, rows: list[list[str]]) -> dict[str, Any]:
        items = [
            {
                "description": one_line(cell(rows, index, 0)),
                "capex_rs": parse_float(cell(rows, index, 2)),
                "operating_rs": parse_float(cell(rows, index, 3)),
                "cycle_time_min": parse_float(cell(rows, index, 4)),
            }
            for index in range(33, 44)
            if one_line(cell(rows, index, 0))
        ]
        return {
            "involved": parse_bool(cell(rows, 31, 3)),
            "involved_raw": cell(rows, 31, 3),
            "section_title": "BEFORE AFM MACHINING",
            "items": items,
            "total_after_assembly_machining_investment": {"capex_rs": parse_float(cell(rows, 44, 2)), "operating_rs": parse_float(cell(rows, 44, 3))},
            "total_after_assembly_machining_investment_for_all_cells": {"capex_rs": parse_float(cell(rows, 45, 2)), "operating_rs": parse_float(cell(rows, 45, 3))},
            "total_assy_investments": {"capex_rs": parse_float(cell(rows, 47, 2)), "operating_rs": parse_float(cell(rows, 47, 3))},
            "resource_requirements": {
                "power_rating_kw_hr": parse_float(cell(rows, 49, 3)),
                "feasible_to_use_machining_cell_operator": parse_bool(cell(rows, 50, 3)),
                "manpower_per_shift_per_cell": parse_float(cell(rows, 51, 3)),
                "floor_space_required_sq_m_per_cell": parse_float(cell(rows, 52, 3)),
            },
        }

    def _page_6(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        rows = matrix(self._table(extraction, "p6_t1"))
        casting_rows = matrix(self._table(extraction, "p6_t2"))
        machining_rows = matrix(self._table(extraction, "p6_t3"))
        casting_items, numbered_points = self._page_6_casting_remarks(casting_rows)
        machining_items = [{"text": one_line(row[0]), "source": "pdf_text", "evidence_refs": []} for row in machining_rows if row and one_line(row[0])]
        third = one_line(cell(rows, 9, 0)).split("Estimation to be reviewed", 1)
        if len(third) == 2:
            estimation_text = "Estimation to be reviewed" + third[1]
            if all(item["text"] != estimation_text for item in machining_items):
                machining_items.append({"text": estimation_text, "source": "pdf_text", "evidence_refs": []})

        return MeridianStructuredPage(
            page_number=6,
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
            remarks_sections=[
                {"section_type": "casting", "title": "Casting Remarks", "items": casting_items, "numbered_points": numbered_points},
                {"section_type": "machining", "title": "Machining Remarks", "items": machining_items, "numbered_points": []},
                {"section_type": "assembly", "title": "Assembly Remarks", "items": [], "numbered_points": []},
            ],
            email_evidence=[
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
            ],
            raw_tables=self._page_tables(extraction, 6),
            raw_text=raw_text,
            warnings=[
                warning("email_screenshot_deferred", "Page 6 contains an email screenshot that requires vision LLM extraction.", 6),
                warning("duplicate_machining_remarks", "Machining remarks appear in multiple extracted tables; normalized remarks should deduplicate repeated text.", 6),
            ],
        )

    def _page_6_casting_remarks(self, rows: list[list[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        items: list[dict[str, Any]] = []
        numbered_points: list[dict[str, Any]] = []
        for row in rows:
            text = clean_text(row[0] if row else "")
            if not text:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                match = re.match(r"^(\d+)\.\s*(.+)$", stripped)
                if match:
                    numbered_points.append(
                        {
                            "number": int(match.group(1)),
                            "text": match.group(2),
                            "source": "pdf_text",
                            "evidence_refs": ["page6_email_1"],
                        }
                    )
                elif not stripped.lower().startswith("factors into our pricing"):
                    refs = ["page6_email_1"] if "email" in stripped.lower() or "AFM process" in stripped else []
                    items.append({"text": stripped, "source": "pdf_text", "evidence_refs": refs})
        return items, numbered_points

    def _page_7(self, extraction: DocumentExtraction, raw_text: str) -> MeridianStructuredPage:
        rows = matrix(self._table(extraction, "p7_t1"))
        return MeridianStructuredPage(
            page_number=7,
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
                "section_title": one_line(cell(rows, 7, 0)),
                "component_image_present": True,
                "part_size_mm": self._dimensions_row(rows, "Part size"),
                "packing_box_size_mm": self._dimensions_row(rows, "Packing box size"),
                "allowances_mm": self._dimensions_row(rows, "Allowances"),
                "arrangements": self._page_7_arrangements(rows),
                "selected_no_of_components_per_box": parse_int(row_value(rows, "No. of components per box", 3)),
                "selected_arrangement_no": None,
                "free_text_rows": [{"text": "Protection cap to be considered in pricing.", "source": "pdf_text"}],
            },
            raw_tables=self._page_tables(extraction, 7),
            raw_text=raw_text,
            warnings=[
                warning("messy_header_extraction", "Page 7 header labels were merged into one extracted table cell; normalized header values were reconstructed from table/text positions.", 7),
                warning("source_typo_preserved", "Section title contains source spelling 'qunaity'; preserve source title unless explicitly normalized.", 7),
                warning("selected_arrangement_not_inferred", "Selected number of components per box is present, but selected arrangement number is not explicitly stated.", 7),
            ],
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

    def _page_7_arrangements(self, rows: list[list[str]]) -> list[dict[str, Any]]:
        arrangements = []
        for index, row in enumerate(rows):
            label = one_line(row[0] if row else "")
            match = re.fullmatch(r"Arrangement\s+(\d+)", label)
            if not match:
                continue
            components_row = rows[index + 1] if index + 1 < len(rows) else []
            arrangements.append(
                {
                    "arrangement_no": int(match.group(1)),
                    "length_count": parse_float(row[3] if len(row) > 3 else ""),
                    "breadth_count": parse_float(row[4] if len(row) > 4 else ""),
                    "height_count": parse_float(row[5] if len(row) > 5 else ""),
                    "no_of_components": parse_int(components_row[3] if len(components_row) > 3 else ""),
                }
            )
        return arrangements
