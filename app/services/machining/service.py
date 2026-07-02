"""Public entry point for machining-operation extraction."""

from app.models import MachiningOperationsResponse

from .extractor import ExtractionError, extract_operations


def extract_machining_operations(pdf_bytes: bytes, step_path: str) -> MachiningOperationsResponse:
    """Extract a machining operation plan from drawing PDF bytes and a STEP file path."""
    return extract_operations(pdf_bytes, step_path)
