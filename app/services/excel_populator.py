import io

import openpyxl
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from app.core.config import Settings
from app.core.excel_mapping import (
    CELL_PAGE,
    CELL_FIELD_KEYS,
    CELL_FIELD_LABELS,
    CELL_SOURCE_TYPES,
    EXCEL_MAPPING,
    EXCEL_SOURCE_MAPPING,
    FORMULA_CELLS,
    set_cell_value,
)
from app.core.provenance import ProvenanceRecorder
from app.models import DocumentExtraction, FieldProvenance, MeridianExtractionResponse
from app.services.errors import ExtractorError
from app.services.meridian import FIELD_PROVENANCE_SOURCES, cell_at, cell_by_index, matrix_cells
from app.services.null_classifier import blocks_approval, classify_null_cell

POPULATED_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
FORMULA_FILL = PatternFill(start_color="D6E4F7", end_color="D6E4F7", fill_type="solid")
NULL_BLOCKING_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
NULL_INFO_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")


def _apply_fill(sheet, coord: str, fill: PatternFill) -> None:
    """Apply fill to coord, expanding across any merged range it belongs to."""
    cell_obj = sheet[coord]
    for merged_range in sheet.merged_cells.ranges:
        if cell_obj.coordinate in merged_range:
            for row in sheet[str(merged_range)]:
                for c in row:
                    c.fill = fill
            return
    cell_obj.fill = fill


def _write_cell(sheet, coord: str, val) -> None:
    """Write value and apply populated fill color."""
    set_cell_value(sheet, coord, val)
    _apply_fill(sheet, coord, POPULATED_FILL)


def _clear_fill(sheet, coord: str) -> None:
    _apply_fill(sheet, coord, PatternFill(fill_type=None))


def _write_formula_cell(sheet, coord: str, formula: str) -> None:
    set_cell_value(sheet, coord, formula)
    _apply_fill(sheet, coord, FORMULA_FILL)


def _apply_static_formula_cache_fixes(sheet) -> None:
    if _is_missing_excel_value(sheet["D13"].value) and _is_missing_excel_value(sheet["I53"].value):
        set_cell_value(sheet, "I17", 0)
        _clear_fill(sheet, "I17")


_PRIORITY_FILLS = {"FFC6EFCE", "FFFFC7CE", "FFD9D9D9"}  # green, red, grey — do not override


def _apply_template_formula_fills(sheet) -> None:
    """Apply blue fill to every template-native formula cell not already colored."""
    for row in sheet.iter_rows():
        for cell in row:
            if not (isinstance(cell.value, str) and cell.value.startswith("=")):
                continue
            fg = cell.fill.fgColor.rgb if cell.fill and cell.fill.fill_type not in (None, "none") else None
            if fg not in _PRIORITY_FILLS and fg != "FFD6E4F7":
                cell.fill = FORMULA_FILL


def _apply_null_fill(sheet, coord: str, is_blocking: bool) -> None:
    _apply_fill(sheet, coord, NULL_BLOCKING_FILL if is_blocking else NULL_INFO_FILL)


def _is_missing_excel_value(val) -> bool:
    return val is None or (isinstance(val, str) and val.strip() == "")


def _merged_anchor_map(sheet) -> dict[str, str]:
    """Map every covered (non-anchor) merged cell coord to its range's anchor.

    Some equipment "units" columns in the master sheet merge several rows into a
    single cell (e.g. L23:L24, L28:L31) and the in-sheet formulas reference the
    anchor. Multiple mapped cells therefore land in one physical cell; writing a
    non-anchor would silently clobber the anchor's value. This map lets the
    populate pass redirect every write to the anchor and keep the first non-empty
    value (mirroring how the master carries one shared value per merged group)."""
    out: dict[str, str] = {}
    for merged_range in sheet.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        anchor = f"{get_column_letter(min_col)}{min_row}"
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                coord = f"{get_column_letter(col)}{row}"
                if coord != anchor:
                    out[coord] = anchor
    return out


def _resolve_mapped_values(sheet, extraction: MeridianExtractionResponse):
    """Compute the value to write for every non-formula mapped cell, collapsing
    merged groups so the anchor keeps the first non-empty value in the group.

    Returns (winners, owners):
      winners[anchor_or_standalone] = (source_coord, value)  — cells that got a value
      owners = ordered list of cells that own a provenance record (anchors +
               standalone cells; covered non-anchor cells are excluded)."""
    anchor_of = _merged_anchor_map(sheet)
    winners: dict[str, tuple[str, object]] = {}
    owners: list[str] = []
    for coord in EXCEL_MAPPING:
        if coord in FORMULA_CELLS:
            continue
        target = anchor_of.get(coord, coord)
        if target not in anchor_of and target not in owners:
            owners.append(target)
        val = EXCEL_MAPPING[coord](extraction)
        if _is_missing_excel_value(val) or target in winners:
            continue
        winners[target] = (coord, val)
    return winners, owners


def _formula_inputs_present(sheet, inputs: list[str]) -> bool:
    return all(not _is_missing_excel_value(sheet[coord].value) for coord in inputs)


def _is_aggregate_formula(formula: str) -> bool:
    """Aggregates (SUM/MAX/…) tolerate blank inputs — Excel treats them as 0 — so
    they are always safe to write as a formula and must never fall back to a static
    value (which would disagree with the line items being aggregated)."""
    head = formula.lstrip("=+ ").upper()
    return head.startswith(("SUM(", "MAX(", "MIN(", "AVERAGE(", "COUNT("))


def _resolve_formula_cells(sheet, extraction: MeridianExtractionResponse) -> dict[str, str]:
    statuses: dict[str, str] = {}

    for _ in range(3):
        changed = False
        for coord, (formula, inputs) in FORMULA_CELLS.items():
            before_value = sheet[coord].value
            before_status = statuses.get(coord)

            if _is_aggregate_formula(formula) or _formula_inputs_present(sheet, inputs):
                _write_formula_cell(sheet, coord, formula)
                statuses[coord] = "formula"
            elif coord in EXCEL_MAPPING:
                fallback_value = EXCEL_MAPPING[coord](extraction)
                if not _is_missing_excel_value(fallback_value):
                    _write_cell(sheet, coord, fallback_value)
                    statuses[coord] = "formula_fallback"
                else:
                    set_cell_value(sheet, coord, None)
                    _clear_fill(sheet, coord)
                    statuses[coord] = "blank"
            else:
                set_cell_value(sheet, coord, None)
                _clear_fill(sheet, coord)
                statuses[coord] = "blank"

            if before_value != sheet[coord].value or before_status != statuses.get(coord):
                changed = True

        if not changed:
            break

    return statuses


def _load_workbook(template_path):
    if not template_path.exists():
        raise ExtractorError(
            "Excel template not found.",
            status_code=404,
            details={"path": str(template_path)},
        )
    wb = openpyxl.load_workbook(template_path)
    if "Input Sheet" not in wb.sheetnames:
        raise ValueError("Sheet 'Input Sheet' not found in template.")
    return wb


def _strip_sheet_extras(sheet) -> None:
    sheet._images = []
    if hasattr(sheet, "_drawings"):
        sheet._drawings = []
    sheet.legacy_drawing = None
    for row in sheet.iter_rows():
        for cell in row:
            if cell.comment:
                cell.comment = None


def _pdf_cell_record(
    coord,
    field_key,
    label,
    val,
    pdf_filename,
    doc_extraction,
    table,
    row_idx,
    col_idx,
    tc,
    reason,
    *,
    source_type="pdf_cell",
    null_category=None,
    is_blocking=False,
) -> FieldProvenance:
    """Construct a pdf_cell FieldProvenance with resolved page/table/bbox."""
    page_meta = next(
        (p for p in doc_extraction.pages if p.page_number == table.page_number), None
    )
    table_index = next(
        (i for i, t in enumerate(doc_extraction.tables) if t.table_id == table.table_id), None
    )
    return FieldProvenance(
        excel_cell=coord,
        field_key=field_key,
        label=label,
        value=val,
        source_type=source_type,
        reason=reason,
        null_category=null_category,
        blocks_approval=is_blocking,
        pdf_filename=pdf_filename,
        page_number=table.page_number,
        table_index=table_index,
        row_index=row_idx,
        col_index=col_idx,
        bbox=tc.bbox,
        page_width=page_meta.width if page_meta else None,
        page_height=page_meta.height if page_meta else None,
    )


def _resolve_source_cell(
    coord: str,
    field_key: str,
    structured: MeridianExtractionResponse,
    doc_extraction: DocumentExtraction,
):
    source_fn = EXCEL_SOURCE_MAPPING.get(coord)
    if source_fn is not None:
        source = source_fn(structured)
        if source:
            table = next(
                (t for t in doc_extraction.tables if t.table_id == source["table_id"]), None
            )
            if table:
                tc = cell_by_index(table, source["row"], source["col"])
                if tc:
                    return table, source["row"], source["col"], tc

    static = FIELD_PROVENANCE_SOURCES.get(field_key)
    if static:
        table_id, row_idx, col_idx = static
        table_id = _static_table_id_for_physical_page(coord, table_id, structured)
        table = next((t for t in doc_extraction.tables if t.table_id == table_id), None)
        if table:
            tc = cell_at(matrix_cells(table), row_idx, col_idx)
            if tc:
                return table, row_idx, col_idx, tc

    return None


def _static_table_id_for_physical_page(
    coord: str,
    table_id: str,
    structured: MeridianExtractionResponse,
) -> str:
    logical_page = CELL_PAGE.get(coord)
    if logical_page is None or "_" not in table_id:
        return table_id

    page = next((p for p in structured.pages if p.page_number == logical_page), None)
    physical_page = getattr(page, "physical_page_number", None) if page else None
    if physical_page is None:
        return table_id

    _, suffix = table_id.split("_", 1)
    return f"p{physical_page}_{suffix}"


def _build_provenance_record(
    coord: str,
    val,
    structured: MeridianExtractionResponse,
    doc_extraction: DocumentExtraction,
    pdf_filename: str,
    *,
    source_type_override: str | None = None,
    display_coord: str | None = None,
) -> FieldProvenance:
    # `coord` drives the field meaning + source lookup (it is the cell whose
    # mapping produced the value); `excel_cell` is where the value physically
    # lives. They differ only for merged groups, where the value is stored on the
    # range anchor but came from a covered cell's mapping.
    excel_cell = display_coord or coord
    field_key = CELL_FIELD_KEYS.get(coord, coord.lower())
    label = CELL_FIELD_LABELS.get(coord, coord)
    source_type = source_type_override or CELL_SOURCE_TYPES.get(coord, "pdf_cell")

    # 1. Explicitly derived / default / unclear cells — correct outcomes, no bbox
    # expected. "unclear_logic" is a NullCategory, not a SourceType: when such a
    # cell actually carries a value it is reported as "inferred" so it never
    # falsely claims a PDF source cell.
    if source_type in ("default", "derived", "unclear_logic"):
        if source_type == "default":
            reason = "Default value configured in Excel mapping."
            emitted_source_type = source_type
        elif source_type == "derived":
            reason = "Value derived/calculated from extracted data."
            emitted_source_type = source_type
        else:
            reason = (
                "Value present, but its derivation logic in the cost model is "
                "unclear — not read directly from a PDF cell."
            )
            emitted_source_type = "inferred"
        return FieldProvenance(
            excel_cell=excel_cell,
            field_key=field_key,
            label=label,
            value=val,
            source_type=emitted_source_type,
            reason=reason,
        )

    # 2. Exact source captured during extraction, with static fallback for older
    # scalar fields that do not yet expose _sources.
    resolved = _resolve_source_cell(coord, field_key, structured, doc_extraction)
    if resolved:
        table, row_idx, col_idx, tc = resolved
        reason = (
            "Formula inputs were missing, so this value was taken directly from the PDF."
            if source_type == "formula_fallback"
            else f"Extracted from table {table.table_id} (page {table.page_number}), "
            f"row {row_idx}, col {col_idx}."
        )
        return _pdf_cell_record(
            excel_cell, field_key, label, val, pdf_filename, doc_extraction, table,
            row_idx, col_idx, tc,
            reason,
            source_type=source_type,
        )

    # 4. Genuinely unlocatable — value was extracted but its cell could not be resolved.
    return FieldProvenance(
        excel_cell=excel_cell,
        field_key=field_key,
        label=label,
        value=val,
        source_type=source_type if source_type == "formula_fallback" else "not_available",
        reason=(
            "Formula inputs were missing, so this value was taken from the PDF; exact location pending."
            if source_type == "formula_fallback"
            else "Extracted from the document; exact location pending."
        ),
        pdf_filename=pdf_filename,
    )


def _build_formula_record(coord: str, formula: str) -> FieldProvenance:
    field_key = CELL_FIELD_KEYS.get(coord, coord.lower())
    label = CELL_FIELD_LABELS.get(coord, coord)
    return FieldProvenance(
        excel_cell=coord,
        field_key=field_key,
        label=label,
        value=formula,
        source_type="formula",
        reason="Calculated by an in-sheet Excel formula after all required inputs were populated.",
        formula=formula,
    )


def _build_null_record(
    coord: str,
    structured: MeridianExtractionResponse,
    doc_extraction: DocumentExtraction,
    pdf_filename: str,
) -> FieldProvenance:
    field_key = CELL_FIELD_KEYS.get(coord, coord.lower())
    label = CELL_FIELD_LABELS.get(coord, coord)
    category = classify_null_cell(coord, structured, doc_extraction)
    is_blocking = blocks_approval(category)
    reason = f"Value is missing; classified as {category}."

    resolved = None
    if category != "page_missing":
        resolved = _resolve_source_cell(coord, field_key, structured, doc_extraction)
    if resolved:
        table, row_idx, col_idx, tc = resolved
        return _pdf_cell_record(
            coord,
            field_key,
            label,
            None,
            pdf_filename,
            doc_extraction,
            table,
            row_idx,
            col_idx,
            tc,
            reason,
            source_type="null",
            null_category=category,
            is_blocking=is_blocking,
        )

    return FieldProvenance(
        excel_cell=coord,
        field_key=field_key,
        label=label,
        value=None,
        source_type="null",
        reason=reason,
        null_category=category,
        blocks_approval=is_blocking,
        pdf_filename=pdf_filename,
    )


class ExcelExportService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def populate(self, extraction: MeridianExtractionResponse) -> bytes:
        try:
            wb = _load_workbook(self.settings.excel_template_path)
            sheet = wb["Input Sheet"]

            winners, _ = _resolve_mapped_values(sheet, extraction)
            for target, (_src_coord, val) in winners.items():
                _write_cell(sheet, target, val)

            _resolve_formula_cells(sheet, extraction)
            _apply_static_formula_cache_fixes(sheet)
            _apply_template_formula_fills(sheet)
            _strip_sheet_extras(sheet)
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output.getvalue()
        except Exception as exc:
            raise ExtractorError("Failed to populate Excel template.", details={"reason": str(exc)}) from exc

    def populate_with_provenance(
        self,
        extraction: MeridianExtractionResponse,
        doc_extraction: DocumentExtraction,
        pdf_filename: str,
    ) -> tuple[bytes, list[FieldProvenance]]:
        try:
            wb = _load_workbook(self.settings.excel_template_path)
            sheet = wb["Input Sheet"]
            recorder = ProvenanceRecorder()

            winners, owners = _resolve_mapped_values(sheet, extraction)
            for coord in owners:
                if coord in winners:
                    src_coord, val = winners[coord]
                    _write_cell(sheet, coord, val)
                    prov = _build_provenance_record(
                        src_coord, val, extraction, doc_extraction, pdf_filename,
                        display_coord=coord,
                    )
                else:
                    prov = _build_null_record(coord, extraction, doc_extraction, pdf_filename)
                    _apply_null_fill(sheet, coord, prov.blocks_approval)
                recorder.record(prov)

            formula_statuses = _resolve_formula_cells(sheet, extraction)
            _apply_static_formula_cache_fixes(sheet)
            for coord, (formula, _) in FORMULA_CELLS.items():
                status = formula_statuses.get(coord)
                if status == "formula":
                    prov = _build_formula_record(coord, formula)
                elif status == "formula_fallback":
                    prov = _build_provenance_record(
                        coord,
                        sheet[coord].value,
                        extraction,
                        doc_extraction,
                        pdf_filename,
                        source_type_override="formula_fallback",
                    )
                else:
                    prov = _build_null_record(coord, extraction, doc_extraction, pdf_filename)
                    _apply_null_fill(sheet, coord, prov.blocks_approval)
                recorder.record(prov)

            _apply_template_formula_fills(sheet)
            _strip_sheet_extras(sheet)
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output.getvalue(), recorder.get_all()
        except Exception as exc:
            raise ExtractorError(
                "Failed to populate Excel template with provenance.", details={"reason": str(exc)}
            ) from exc
