from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BBox = tuple[float, float, float, float]


class WarningSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class ExtractionWarning(BaseModel):
    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.warning
    page_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PageMetadata(BaseModel):
    page_number: int
    width: float
    height: float
    rotation: int
    classification: Literal["vector_text", "image_only", "mixed"]
    text_blocks: int
    text_lines: int
    text_chars: int
    image_count: int
    drawing_count: int
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class TableColumn(BaseModel):
    index: int
    key: str
    label: str | None = None


class TableCell(BaseModel):
    row: int
    column: int
    text: str
    bbox: BBox | None = None
    rowspan: int = 1
    colspan: int = 1
    confidence: float = 1.0
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class TableRow(BaseModel):
    index: int
    cells: list[TableCell]


class ExtractedTable(BaseModel):
    table_id: str
    page_number: int
    title: str | None = None
    bbox: BBox
    columns: list[TableColumn]
    header_row_count: int = 0
    rows: list[TableRow]
    confidence: float
    extraction_method: Literal["lines", "text"] = "lines"
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class DocumentExtraction(BaseModel):
    document_id: str
    filename: str
    sha256: str
    page_count: int
    pages: list[PageMetadata]
    tables: list[ExtractedTable]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    page_count: int
    table_count: int
    cached: bool = False
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class TablesResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    tables: list[ExtractedTable]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class MeridianStructuredPage(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_number: int
    page_type: str
    title: str | None = None
    header: dict[str, Any] = Field(default_factory=dict)
    raw_tables: list[ExtractedTable] = Field(default_factory=list)
    raw_text: str = ""
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class MeridianExtractionResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    pages: list[MeridianStructuredPage]
    raw_tables: list[ExtractedTable] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class ReferenceDocumentResponse(BaseModel):
    configured: bool
    path: str
    document_id: str | None = None
    extracted: bool = False
    message: str | None = None


class FieldSource(BaseModel):
    page_number: int | None = None
    table_id: str | None = None
    row: int | None = None
    column: int | None = None
    text: str | None = None


class NormalizedField(BaseModel):
    value: Any
    source: FieldSource | None = None
    confidence: float = 1.0


class ExcelWrittenCell(BaseModel):
    field: str
    cell: str
    value: Any
    status: Literal["written", "skipped"]
    source: FieldSource | None = None
    message: str | None = None


class ExcelValidatedField(BaseModel):
    field: str
    cell: str | None = None
    calculated_value: Any
    extracted_value: Any | None = None
    status: Literal["validated", "calculated", "mismatch", "missing_inputs"]
    message: str | None = None


class ExcelFillReport(BaseModel):
    job_id: str
    document_id: str
    template_filename: str
    output_filename: str
    sheet_name: str = "Input Sheet"
    written_cells: list[ExcelWrittenCell] = Field(default_factory=list)
    validated_fields: list[ExcelValidatedField] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class ExcelFillResponse(BaseModel):
    job_id: str
    document_id: str
    output_filename: str
    download_url: str
    report: ExcelFillReport
