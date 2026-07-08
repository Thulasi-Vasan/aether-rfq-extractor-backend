"""Request model for the RFQ Estimation PDF report.

The report has a rich default context (the Meridian reference sheet). Callers
send only the sections/fields they have; anything omitted falls back to the
reference default. Each section is a loosely-typed dict so the frontend can map
its stage data directly without the backend having to mirror every cell.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
