from __future__ import annotations

from app.core.excel_mapping import (
    BLOCKING_CATEGORIES,
    CELL_PAGE,
    DERIVED_DEPENDENCIES,
)
from app.models import DocumentExtraction, MeridianExtractionResponse, NullCategory

LOW_TABLE_CONFIDENCE = 0.25


def classify_null_cell(
    coord: str,
    structured: MeridianExtractionResponse,
    doc_extraction: DocumentExtraction,
) -> NullCategory:
    dependency = DERIVED_DEPENDENCIES.get(coord)
    if dependency and dependency(structured) is None:
        return "derived_dependency_missing"

    page_number = CELL_PAGE.get(coord)
    if page_number is None:
        return "data_absent"

    if not _page_present(page_number, doc_extraction):
        return "page_missing"

    if _page_unparseable(page_number, doc_extraction):
        return "extraction_failure"

    return "data_absent"


def blocks_approval(category: NullCategory) -> bool:
    return category in BLOCKING_CATEGORIES


def _page_present(page_number: int, doc_extraction: DocumentExtraction) -> bool:
    return any(page.page_number == page_number for page in doc_extraction.pages)


def _page_unparseable(page_number: int, doc_extraction: DocumentExtraction) -> bool:
    page_meta = next(
        (page for page in doc_extraction.pages if page.page_number == page_number),
        None,
    )
    if page_meta and page_meta.classification == "image_only":
        return True

    page_tables = [
        table for table in doc_extraction.tables if table.page_number == page_number
    ]
    if not page_tables:
        return True
    return all(table.confidence < LOW_TABLE_CONFIDENCE for table in page_tables)
