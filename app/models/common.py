from enum import Enum
from typing import Any

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
