from typing import Literal

from pydantic import BaseModel, Field

EvidenceType = Literal["dimension", "note", "spec", "datum", "classification", "view_ref"]
MatchStatus = Literal["matched", "ambiguous", "not_found"]


class AnchorCandidate(BaseModel):
    """One possible location for an ambiguous evidence match."""

    anchor_text: str
    anchor_bbox: list[float]
    region_bbox: list[float]


class PdfAnchor(BaseModel):
    """Where an evidence item was located on the drawing PDF. ALWAYS present in the
    response (even on failure) so the frontend keeps page/status/confidence and can
    fall back to opening the page. Boxes are nullable when not resolved.

    Coordinates are PDF points, top-left origin: [x0, top, x1, bottom]."""

    page: int | None = Field(None, description="1-based PDF page (best guess even if unmatched).")
    anchor_text: str | None = Field(None, description="Token actually matched.")
    anchor_bbox: list[float] | None = Field(None, description="Tight box on the primary token.")
    region_bbox: list[float] | None = Field(None, description="Expanded context box to highlight.")
    page_size: list[float] | None = Field(None, description="[width, height] for frontend scaling.")
    match_status: MatchStatus = "not_found"
    confidence: float = 0.0
    candidates: list[AnchorCandidate] = Field(
        default_factory=list, description="Alternative locations when match_status is 'ambiguous'."
    )


class DrawingEvidence(BaseModel):
    """A single structured piece of drawing evidence justifying an operation."""

    evidence_text: str = Field(..., description="Human-friendly explanation of the evidence.")
    verbatim_text: str | None = Field(None, description="Most distinctive exact printed token (LLM hint).")
    match_terms: list[str] = Field(
        default_factory=list, description="Exact printed tokens for locating/disambiguating (LLM hint)."
    )
    evidence_type: EvidenceType = Field(..., description="Kind of evidence.")
    sheet: str | None = Field(None, description="Sheet the evidence appears on, e.g. 'Sheet 1'.")
    view_or_detail: str | None = Field(None, description="View/detail ref, e.g. 'Section X-X'.")
    # Filled by the backend pdf_locator (authority for coordinates); always set before response.
    pdf_anchor: PdfAnchor | None = Field(None, description="Resolved PDF location.")


class PartOverview(BaseModel):
    """High-level part overview read from the drawing. Fields nullable to avoid
    hallucination when a title-block field is not readable."""

    part_name: str | None = None
    part_number: str | None = None
    revision: str | None = None
    input_blank: str | None = Field(None, description="Casting vs semi-finished, from Item Identifier/BOM.")
    material: str | None = Field(None, description="From the Associated Specifications.")
    drawing_standard: str | None = Field(None, description="From the title block, e.g. 'ASME Y14.5-2009'.")


class LLMOperation(BaseModel):
    """A single operation as inferred by the LLM (the structured tool output)."""

    opn_no: int = Field(..., description="Operation number, e.g. 20, 30, 40 ...")
    operation_name: str = Field(..., description="Exact operation/work-center name selected from inventory.")
    operation_description: str = Field(..., description="One plain-language sentence describing the work done.")
    why_machine_process: str = Field(..., description="Which machine/process and why, tied to drawing evidence.")
    sequence_rationale: str = Field(..., description="Why at this point in sequence; any drawing-mandated order.")
    source_of_truth: list[DrawingEvidence] = Field(
        default_factory=list, description="Structured drawing evidence (never STEP geometry)."
    )


class LLMResult(BaseModel):
    """Full structured payload returned by the forced Bedrock tool call."""

    part_overview: PartOverview = Field(default_factory=PartOverview)
    operations: list[LLMOperation] = Field(default_factory=list)


class StepFeatureSummary(BaseModel):
    """Lightweight 3D feature summary extracted from the STEP file via pythonOCC."""

    bounding_box_mm: list[float]
    volume_mm3: float
    estimated_weight_kg: float
    num_solids: int
    num_faces: int
    num_cylindrical_faces: int
    num_planar_faces: int
    num_conical_faces: int
    num_freeform_faces: int
    cylinder_radius_histogram_mm: dict[str, int] = Field(default_factory=dict)


class MachiningOperationsResponse(BaseModel):
    """Response for the standalone machining-operation API."""

    part_overview: PartOverview | None = None
    part_number: str | None = None
    model_id: str
    operations: list[LLMOperation]
    step_features: StepFeatureSummary | None = None
