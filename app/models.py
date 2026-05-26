from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

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


class ReferenceDocumentResponse(BaseModel):
    configured: bool
    path: str
    document_id: str | None = None
    extracted: bool = False
    message: str | None = None


class BundleFile(BaseModel):
    filename: str
    sha256: str
    file_type: Literal["pdf", "step"]
    part_number: str | None = None
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class PartSpecification(BaseModel):
    spec_number: str
    title: str | None = None
    type: str | None = None
    category: str | None = None
    sub_category: str | None = None


class DrawingAuthorization(BaseModel):
    drafter: str | None = None
    drafter_date: str | None = None
    checker: str | None = None
    checker_date: str | None = None
    approver: str | None = None
    approver_date: str | None = None


class BoundingBoxMm(BaseModel):
    x_min: float
    y_min: float
    z_min: float
    x_max: float
    y_max: float
    z_max: float
    length: float
    width: float
    height: float


class CadGeometry(BaseModel):
    source_file: str
    step_product_number: str | None = None
    units: str | None = None
    bounding_box_mm: BoundingBoxMm | None = None
    volume_mm3: float | None = None
    surface_area_mm2: float | None = None
    solid_count: int | None = None
    mass_kg: float | None = None
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class PartProfile(BaseModel):
    part_number: str
    revision: str | None = None
    part_name: str | None = None
    stage: str | None = None
    drawing_category: str | None = None
    state: str | None = None
    company: str | None = None
    classification: str | None = None
    document_generated: str | None = None
    authorization: DrawingAuthorization | None = None
    specifications: list[PartSpecification] = Field(default_factory=list)
    cad_geometry: CadGeometry | None = None
    source_files: list[str] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class BomRelationship(BaseModel):
    parent_part_number: str
    parent_stage: str | None = None
    child_part_number: str
    child_stage: str | None = None
    child_name: str | None = None
    quantity: int | float | str | None = None
    unit_of_measure: str | None = None
    method_of_use: str | None = None
    source_file: str
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class PartBundleExtraction(BaseModel):
    bundle_id: str
    files: list[BundleFile]
    parts: list[PartProfile]
    relationships: list[BomRelationship]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class BasicSourceNote(BaseModel):
    field: str
    source_file: str
    source_type: Literal["pdf", "step", "derived", "internal_mapping"]
    note: str


class BasicPartDetails(BaseModel):
    final_part_no: str | None = None
    part_number: str | None = None
    revision: str | None = None
    part_name: str | None = None
    stage: str | None = None
    drawing_category: str | None = None
    state: str | None = None
    project_name: str | None = None
    company: str | None = None


class BasicMaterialDetails(BaseModel):
    spec_number: str | None = None
    title: str | None = None
    density_g_per_cm3: float | None = None
    density_source: str | None = None


class BasicBomChild(BaseModel):
    part_number: str
    name: str | None = None
    quantity: int | float | str | None = None
    unit_of_measure: str | None = None
    method_of_use: str | None = None


class BasicBomDetails(BaseModel):
    child_part_count: int = 0
    children: list[BasicBomChild] = Field(default_factory=list)


class BasicCadDetails(BaseModel):
    step_product_number: str | None = None
    units: str | None = None
    bounding_box_mm: BoundingBoxMm | None = None
    sorted_lbh_mm: list[float] = Field(default_factory=list)
    volume_mm3: float | None = None
    volume_cm3: float | None = None
    surface_area_mm2: float | None = None
    solid_count: int | None = None


class BasicMassDetails(BaseModel):
    declared_mass_kg: float | None = None
    estimated_mass_kg: float | None = None
    implied_density_g_per_cm3: float | None = None
    density_g_per_cm3: float | None = None
    derivation: str | None = None
    notes: list[str] = Field(default_factory=list)


class BasicViewerFiles(BaseModel):
    pdf_url: str
    step_url: str


class BasicExtraction(BaseModel):
    extraction_id: str
    part: BasicPartDetails
    material: BasicMaterialDetails
    bom: BasicBomDetails
    cad: BasicCadDetails
    mass: BasicMassDetails
    viewer_files: BasicViewerFiles
    sources: list[BasicSourceNote] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
