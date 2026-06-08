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

POPULATED_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")


def _apply_fill(sheet, coord: str) -> None:
    """Apply POPULATED_FILL to coord, expanding across any merged range it belongs to."""
    cell_obj = sheet[coord]
    for merged_range in sheet.merged_cells.ranges:
        if cell_obj.coordinate in merged_range:
            for row in sheet[str(merged_range)]:
                for c in row:
                    c.fill = POPULATED_FILL
            return
    cell_obj.fill = POPULATED_FILL


def _write_cell(sheet, coord: str, val) -> None:
    """Write value and apply populated fill color."""
    set_cell_value(sheet, coord, val)
    _apply_fill(sheet, coord)


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
    coord, field_key, label, val, pdf_filename, doc_extraction, table, row_idx, col_idx, tc, reason
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
        source_type="pdf_cell",
        reason=reason,
        pdf_filename=pdf_filename,
        page_number=table.page_number,
        table_index=table_index,
        row_index=row_idx,
        col_index=col_idx,
        bbox=tc.bbox,
        page_width=page_meta.width if page_meta else None,
        page_height=page_meta.height if page_meta else None,
    )


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

    # 2. Exact source captured during extraction (_sources on the structured item).
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
                    return _pdf_cell_record(
                        coord, field_key, label, val, pdf_filename, doc_extraction, table,
                        source["row"], source["col"], tc,
                        f"Extracted from table {table.table_id} (page {table.page_number}), "
                        f"row {source['row']}, col {source['col']}.",
                    )

    # 3. Static source index — temporary safety net for header/die/power scalars.
    static = FIELD_PROVENANCE_SOURCES.get(field_key)
    if static:
        table_id, row_idx, col_idx = static
        table = next((t for t in doc_extraction.tables if t.table_id == table_id), None)
        if table:
            tc = cell_at(matrix_cells(table), row_idx, col_idx)
            if tc:
                return _pdf_cell_record(
                    coord, field_key, label, val, pdf_filename, doc_extraction, table,
                    row_idx, col_idx, tc,
                    f"Extracted from table {table_id} (page {table.page_number}), "
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
