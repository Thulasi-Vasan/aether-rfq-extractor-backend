from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import BBox, ExtractionWarning
from .documents import ExtractedTable


class MeridianStructuredPage(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_number: int
    physical_page_number: int | None = None
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


SourceType = Literal[
    "pdf_cell",
    "derived",
    "default",
    "inferred",
    "formula",
    "formula_fallback",
    "not_available",
    "null",
]
NullCategory = Literal[
    "data_absent",
    "derived_dependency_missing",
    "page_missing",
    "extraction_failure",
    "not_applicable",
    "unclear_logic",
]


class FieldProvenance(BaseModel):
    excel_cell: str
    field_key: str
    label: str
    value: Any
    source_type: SourceType
    reason: str
    formula: str | None = None
    null_category: NullCategory | None = None
    blocks_approval: bool = False
    pdf_filename: str | None = None
    page_number: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    col_index: int | None = None
    bbox: BBox | None = None
    page_width: float | None = None
    page_height: float | None = None
