"""Request model for the RFQ Estimation PDF report.

The report has a rich default context (the Meridian reference sheet). Callers
send only the sections/fields they have; anything omitted falls back to the
reference default. Each section is a loosely-typed dict so the frontend can map
its stage data directly without the backend having to mirror every cell.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import ErrorDetail, ExtractionWarning


class RfqEstimationRequest(BaseModel):
    """Stage data (mostly from frontend stages 1-3) to overlay on the reference."""

    model_config = ConfigDict(extra="allow")

    header: dict[str, Any] | None = Field(
        default=None,
        description="RFQ header fields shown on every page (rfq_no, customer, date, part image, ...).",
    )
    casting: dict[str, Any] | None = Field(default=None, description="Casting / GDC page overrides.")
    machining: dict[str, Any] | None = Field(default=None, description="Machining estimation page overrides.")
    process_planning: dict[str, Any] | None = Field(default=None, description="Process planning page overrides.")
    assembly: dict[str, Any] | None = Field(default=None, description="Assembly estimation page overrides.")
    remarks: dict[str, Any] | None = Field(default=None, description="Remarks page overrides.")
    packing: dict[str, Any] | None = Field(default=None, description="Packing estimation page overrides.")

    def as_overrides(self) -> dict[str, Any]:
        """Return the payload as a plain override dict (drops unset sections)."""
        return self.model_dump(exclude_none=True)


class PartImageResponse(BaseModel):
    """A rendered part snapshot, ready to drop into ``header.part_image``."""

    part_image: str = Field(description="data: URI (PNG) rendered from the STEP file.")


class GeneratedRfqCostEstimationResponse(BaseModel):
    """Result of auto-running the Cost Estimation flow on a generated RFQ Estimation PDF.

    ``document_id`` is the same identifier the manual upload flow uses, so the existing
    ``/v1/documents/{document_id}/...`` routes (meridian, export-excel, provenance, pdf)
    work unchanged against it.
    """

    rfq_payload_hash: str = Field(
        description="Hash of the RFQ payload used as the idempotency key (not the PDF bytes, "
        "which embed a render timestamp and differ across identical calls)."
    )
    pdf_filename: str
    document_id: str | None = Field(
        default=None, description="Cost estimation document id; also the generated RFQ PDF reference."
    )
    status: Literal["success", "failed", "pending"]
    cached: bool = Field(
        default=False, description="True if this is a replay of a previous approval for the same payload."
    )
    page_map: dict[int, int] = Field(default_factory=dict, description="Logical page -> physical page.")
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    blocking_fields: list[str] = Field(
        default_factory=list, description="Excel cells whose null category blocks approval, if any."
    )
    error: ErrorDetail | None = None
