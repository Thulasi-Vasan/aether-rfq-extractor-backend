from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Iterable

import fitz
import pdfplumber
from fastapi import UploadFile

from app.core.config import Settings
from app.models import (
    BBox,
    DocumentExtraction,
    ExtractedTable,
    ExtractionWarning,
    PageMetadata,
    TableCell,
    TableColumn,
    TableRow,
    WarningSeverity,
)
from app.services.errors import EncryptedPdfError, ExtractorError, InvalidPdfError
from app.services.storage import DocumentStore, document_id_from_sha256, sha256_file


LINE_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 5,
    "text_tolerance": 3,
}

TEXT_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 4,
    "join_tolerance": 4,
    "intersection_tolerance": 6,
    "min_words_vertical": 3,
    "min_words_horizontal": 1,
    "text_tolerance": 3,
}

MAX_TITLE_DISTANCE = 36


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def slug_key(value: str | None, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    if not text:
        return fallback
    return text[:48]


def bbox_from_cells(cells: Iterable[BBox]) -> BBox:
    cells = list(cells)
    return (
        min(cell[0] for cell in cells),
        min(cell[1] for cell in cells),
        max(cell[2] for cell in cells),
        max(cell[3] for cell in cells),
    )


def bbox_to_tuple(value: object) -> BBox | None:
    if not value:
        return None
    x0, top, x1, bottom = value  # pdfplumber table cells are page-local top-left coordinates.
    return (round(float(x0), 3), round(float(top), 3), round(float(x1), 3), round(float(bottom), 3))


class PdfExtractionService:
    def __init__(self, settings: Settings, store: DocumentStore) -> None:
        self.settings = settings
        self.store = store

    async def save_upload_to_temp(self, upload: UploadFile) -> Path:
        if upload.content_type and upload.content_type not in {"application/pdf", "application/octet-stream"}:
            raise InvalidPdfError("Only PDF uploads are supported.", details={"content_type": upload.content_type})

        suffix = ".pdf"
        written = 0
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        try:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > self.settings.max_upload_bytes:
                    raise InvalidPdfError(
                        "Uploaded PDF exceeds the configured size limit.",
                        details={"max_upload_bytes": self.settings.max_upload_bytes},
                    )
                tmp.write(chunk)
        finally:
            tmp.close()

        if written == 0:
            tmp_path.unlink(missing_ok=True)
            raise InvalidPdfError("Uploaded file is empty.")
        return tmp_path

    def extract_upload(self, source_path: Path, filename: str, *, force_reextract: bool = False) -> tuple[DocumentExtraction, bool]:
        digest = sha256_file(source_path)
        document_id = document_id_from_sha256(digest)

        if self.store.has_extraction(document_id) and not force_reextract:
            return self.store.load_extraction(document_id), True

        upload_path = self.store.save_upload(source_path, document_id)
        extraction = self.extract_pdf(upload_path, document_id=document_id, filename=filename, sha256=digest)
        self.store.save_extraction(extraction)
        return extraction, False

    def extract_reference(self, *, force_reextract: bool = False) -> tuple[DocumentExtraction, bool]:
        path = self.settings.reference_pdf_path
        if not path.exists():
            raise InvalidPdfError("Reference PDF path does not exist.", details={"path": str(path)})
        return self.extract_upload(path, path.name, force_reextract=force_reextract)

    def extract_pdf(self, path: Path, *, document_id: str, filename: str, sha256: str) -> DocumentExtraction:
        try:
            fitz_doc = fitz.open(path)
        except Exception as exc:
            raise InvalidPdfError("The uploaded file could not be read as a PDF.") from exc

        try:
            if fitz_doc.is_encrypted:
                raise EncryptedPdfError("Password-protected PDFs are not supported in v1.")
            pages = self._preflight_pages(fitz_doc)
        finally:
            fitz_doc.close()

        tables: list[ExtractedTable] = []
        warnings: list[ExtractionWarning] = []

        try:
            with pdfplumber.open(path) as pdf:
                for index, page in enumerate(pdf.pages, start=1):
                    page_tables = self._extract_page_tables(page, index)
                    tables.extend(page_tables)
                    self.store.write_debug_json(
                        document_id,
                        f"page_{index}_tables.json",
                        [table.model_dump(mode="json") for table in page_tables],
                    )
        except EncryptedPdfError:
            raise
        except Exception as exc:
            raise ExtractorError("Table extraction failed.", details={"reason": str(exc)}) from exc

        for page in pages:
            if page.classification == "image_only":
                warning = ExtractionWarning(
                    code="image_only_page",
                    message="Page has no extractable vector text; OCR is not enabled in v1.",
                    page_number=page.page_number,
                    severity=WarningSeverity.warning,
                )
                page.warnings.append(warning)
                warnings.append(warning)

        return DocumentExtraction(
            document_id=document_id,
            filename=filename,
            sha256=sha256,
            page_count=len(pages),
            pages=pages,
            tables=tables,
            warnings=warnings,
        )

    def _preflight_pages(self, doc: fitz.Document) -> list[PageMetadata]:
        pages: list[PageMetadata] = []
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            text_dict = page.get_text("dict")
            text_blocks = [block for block in text_dict.get("blocks", []) if block.get("type") == 0]
            text_lines = sum(len(block.get("lines", [])) for block in text_blocks)
            text_chars = len(page.get_text("text").strip())
            image_count = len(page.get_images(full=True))
            drawings = page.get_drawings()
            if text_chars and image_count:
                classification = "mixed"
            elif text_chars:
                classification = "vector_text"
            else:
                classification = "image_only"

            pages.append(
                PageMetadata(
                    page_number=page_index + 1,
                    width=round(float(page.rect.width), 3),
                    height=round(float(page.rect.height), 3),
                    rotation=int(page.rotation),
                    classification=classification,
                    text_blocks=len(text_blocks),
                    text_lines=text_lines,
                    text_chars=text_chars,
                    image_count=image_count,
                    drawing_count=len(drawings),
                )
            )
        return pages

    def _extract_page_tables(self, page: pdfplumber.page.Page, page_number: int) -> list[ExtractedTable]:
        line_tables = self._find_tables(page, page_number, LINE_TABLE_SETTINGS, "lines")
        if line_tables:
            return line_tables

        words = page.extract_words() or []
        if len(words) < 6:
            return []

        text_tables = self._find_tables(page, page_number, TEXT_TABLE_SETTINGS, "text")
        for table in text_tables:
            table.warnings.append(
                ExtractionWarning(
                    code="text_alignment_table",
                    message="Table boundaries were inferred from text alignment.",
                    page_number=page_number,
                    severity=WarningSeverity.warning,
                )
            )
            table.confidence = min(table.confidence, 0.72)
        return text_tables

    def _find_tables(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        settings: dict,
        method: str,
    ) -> list[ExtractedTable]:
        found = page.find_tables(table_settings=settings)
        extracted: list[ExtractedTable] = []
        for table_index, table in enumerate(found, start=1):
            candidate = self._normalize_table(page, table, page_number, table_index, method)
            if candidate:
                extracted.append(candidate)
        return extracted

    def _normalize_table(
        self,
        page: pdfplumber.page.Page,
        table: pdfplumber.table.Table,
        page_number: int,
        table_index: int,
        method: str,
    ) -> ExtractedTable | None:
        matrix = table.extract() or []
        if not matrix:
            return None

        normalized_rows = [[normalize_text(cell) for cell in row] for row in matrix]
        max_cols = max((len(row) for row in normalized_rows), default=0)
        if max_cols == 0:
            return None

        normalized_rows = [row + [""] * (max_cols - len(row)) for row in normalized_rows]
        non_empty_cells = sum(1 for row in normalized_rows for cell in row if cell)
        if non_empty_cells < 2:
            return None

        cell_bbox_rows = self._extract_cell_bbox_rows(table, len(normalized_rows), max_cols)
        present_bboxes = [
            bbox
            for row in cell_bbox_rows
            for bbox in row
            if bbox is not None
        ]
        table_bbox = bbox_to_tuple(table.bbox) or bbox_from_cells(present_bboxes)

        warnings: list[ExtractionWarning] = []
        if non_empty_cells / max(1, (len(normalized_rows) * max_cols)) < 0.2:
            warnings.append(
                ExtractionWarning(
                    code="sparse_table",
                    message="Most detected cells are empty; table may need review.",
                    page_number=page_number,
                    severity=WarningSeverity.warning,
                )
            )

        columns = self._build_columns(normalized_rows)
        rows = self._build_rows(normalized_rows, cell_bbox_rows, max_cols)
        title = self._infer_title(page, table_bbox, normalized_rows)
        confidence = self._score_table(method, normalized_rows, warnings)

        return ExtractedTable(
            table_id=f"p{page_number}_t{table_index}",
            page_number=page_number,
            title=title,
            bbox=table_bbox,
            columns=columns,
            header_row_count=1 if any(column.label for column in columns) else 0,
            rows=rows,
            confidence=confidence,
            extraction_method=method,  # type: ignore[arg-type]
            warnings=warnings,
        )

    def _build_columns(self, rows: list[list[str]]) -> list[TableColumn]:
        header = rows[0] if rows else []
        columns: list[TableColumn] = []
        used: set[str] = set()
        for index, label in enumerate(header):
            cleaned = label.replace("\n", " ").strip() or None
            key = slug_key(cleaned, f"col_{index + 1}")
            if key in used:
                key = f"{key}_{index + 1}"
            used.add(key)
            columns.append(TableColumn(index=index, key=key, label=cleaned))
        return columns

    def _extract_cell_bbox_rows(
        self,
        table: pdfplumber.table.Table,
        row_count: int,
        max_cols: int,
    ) -> list[list[BBox | None]]:
        bbox_rows: list[list[BBox | None]] = []
        for row in table.rows[:row_count]:
            row_bboxes = [bbox_to_tuple(cell) for cell in row.cells[:max_cols]]
            row_bboxes.extend([None] * (max_cols - len(row_bboxes)))
            bbox_rows.append(row_bboxes)
        while len(bbox_rows) < row_count:
            bbox_rows.append([None] * max_cols)
        return bbox_rows

    def _build_rows(self, rows: list[list[str]], bboxes: list[list[BBox | None]], max_cols: int) -> list[TableRow]:
        rendered_rows: list[TableRow] = []
        for row_index, row in enumerate(rows):
            cells: list[TableCell] = []
            for col_index in range(max_cols):
                bbox = bboxes[row_index][col_index] if row_index < len(bboxes) else None
                cells.append(
                    TableCell(
                        row=row_index,
                        column=col_index,
                        text=row[col_index],
                        bbox=bbox,
                        rowspan=1,
                        colspan=1,
                        confidence=0.9 if row[col_index] else 0.75,
                    )
                )
            rendered_rows.append(TableRow(index=row_index, cells=cells))
        return rendered_rows

    def _infer_title(self, page: pdfplumber.page.Page, table_bbox: BBox, rows: list[list[str]]) -> str | None:
        x0, top, x1, _ = table_bbox
        words = page.extract_words(extra_attrs=["fontname", "size"]) or []
        above_words = [
            word
            for word in words
            if x0 - 8 <= float(word["x0"]) <= x1 + 8
            and 0 <= top - float(word["bottom"]) <= MAX_TITLE_DISTANCE
        ]
        if above_words:
            above_words.sort(key=lambda word: (round(float(word["top"])), float(word["x0"])))
            title = " ".join(word["text"] for word in above_words).strip()
            if len(title) >= 3:
                return title

        first_row = [cell for cell in (rows[0] if rows else []) if cell]
        if len(first_row) == 1:
            return first_row[0].replace("\n", " ")
        return None

    def _score_table(self, method: str, rows: list[list[str]], warnings: list[ExtractionWarning]) -> float:
        base = 0.86 if method == "lines" else 0.7
        if len(rows) >= 3:
            base += 0.04
        if warnings:
            base -= 0.08
        return max(0.1, min(0.98, round(base, 2)))
