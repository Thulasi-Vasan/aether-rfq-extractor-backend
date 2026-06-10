import io

import openpyxl
from openpyxl.styles import PatternFill

from app.core.config import Settings
from app.core.excel_mapping import (
    CELL_FIELD_KEYS,
    CELL_FIELD_LABELS,
    CELL_SOURCE_TYPES,
    EXCEL_MAPPING,
    EXCEL_SOURCE_MAPPING,
    set_cell_value,
)
from app.core.provenance import ProvenanceRecorder
from app.models import DocumentExtraction, FieldProvenance, MeridianExtractionResponse
from app.services.errors import ExtractorError
from app.services.meridian import FIELD_PROVENANCE_SOURCES, cell_at, cell_by_index, matrix_cells
from app.services.null_classifier import blocks_approval, classify_null_cell

POPULATED_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
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


def _apply_null_fill(sheet, coord: str, is_blocking: bool) -> None:
    _apply_fill(sheet, coord, NULL_BLOCKING_FILL if is_blocking else NULL_INFO_FILL)


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
        table = next((t for t in doc_extraction.tables if t.table_id == table_id), None)
        if table:
            tc = cell_at(matrix_cells(table), row_idx, col_idx)
            if tc:
                return table, row_idx, col_idx, tc

    return None


def _build_provenance_record(
    coord: str,
    val,
    structured: MeridianExtractionResponse,
    doc_extraction: DocumentExtraction,
    pdf_filename: str,
) -> FieldProvenance:
    field_key = CELL_FIELD_KEYS.get(coord, coord.lower())
    label = CELL_FIELD_LABELS.get(coord, coord)
    source_type = CELL_SOURCE_TYPES.get(coord, "pdf_cell")

    # 1. Explicitly derived / default cells — correct outcomes, no bbox expected.
    if source_type in ("default", "derived"):
        reason = (
            "Default value configured in Excel mapping."
            if source_type == "default"
            else "Value derived/calculated from extracted data."
        )
        return FieldProvenance(
            excel_cell=coord,
            field_key=field_key,
            label=label,
            value=val,
            source_type=source_type,
            reason=reason,
        )

    # 2. Exact source captured during extraction, with static fallback for older
    # scalar fields that do not yet expose _sources.
    resolved = _resolve_source_cell(coord, field_key, structured, doc_extraction)
    if resolved:
        table, row_idx, col_idx, tc = resolved
        return _pdf_cell_record(
            coord, field_key, label, val, pdf_filename, doc_extraction, table,
            row_idx, col_idx, tc,
            f"Extracted from table {table.table_id} (page {table.page_number}), "
            f"row {row_idx}, col {col_idx}.",
        )

    # 4. Genuinely unlocatable — value was extracted but its cell could not be resolved.
    return FieldProvenance(
        excel_cell=coord,
        field_key=field_key,
        label=label,
        value=val,
        source_type="not_available",
        reason="Extracted from the document; exact location pending.",
        pdf_filename=pdf_filename,
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

            for coord, extractor_func in EXCEL_MAPPING.items():
                val = extractor_func(extraction)
                if val is not None:
                    _write_cell(sheet, coord, val)

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

            for coord, extractor_func in EXCEL_MAPPING.items():
                val = extractor_func(extraction)
                if val is not None:
                    _write_cell(sheet, coord, val)
                    prov = _build_provenance_record(coord, val, extraction, doc_extraction, pdf_filename)
                else:
                    prov = _build_null_record(coord, extraction, doc_extraction, pdf_filename)
                    _apply_null_fill(sheet, coord, prov.blocks_approval)
                recorder.record(prov)

            _strip_sheet_extras(sheet)
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output.getvalue(), recorder.get_all()
        except Exception as exc:
            raise ExtractorError(
                "Failed to populate Excel template with provenance.", details={"reason": str(exc)}
            ) from exc
