from __future__ import annotations

from app.core.excel_mapping import (
    BLOCKING_CATEGORIES,
    CELL_PAGE,
    DERIVED_DEPENDENCIES,
    PAGE_ANCHOR_TABLES,
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

    if not _page_content_present(page_number, doc_extraction):
        return "page_missing"

    if _page_unparseable(page_number, doc_extraction):
        return "extraction_failure"

    return "data_absent"


def blocks_approval(category: NullCategory) -> bool:
    return category in BLOCKING_CATEGORIES


def _page_content_present(page_number: int, doc_extraction: DocumentExtraction) -> bool:
    """Check that the expected content for this page actually exists in the extraction.

    Uses the anchor table ID (e.g. p3_t1 for page 3) rather than the physical page
    number — this survives PDF page renumbering when a page is removed mid-document.

    A page that is physically present but image-only (no table extracted) is treated
    as "present" so the caller can classify it as extraction_failure rather than
    page_missing.
    """
    anchor = PAGE_ANCHOR_TABLES.get(page_number)
    if anchor:
        if any(t.table_id == anchor for t in doc_extraction.tables):
            return True
        # No anchor table, but the page physically exists as image-only — it's present
        # but unparseable; _page_unparseable will handle it as extraction_failure.
        page_meta = next(
            (p for p in doc_extraction.pages if p.page_number == page_number), None
        )
        if page_meta and page_meta.classification == "image_only":
            return True
        return False
    return any(page.page_number == page_number for page in doc_extraction.pages)


def _page_unparseable(page_number: int, doc_extraction: DocumentExtraction) -> bool:
    # Always check page metadata first — image_only is the clearest extraction failure.
    page_meta = next(
        (p for p in doc_extraction.pages if p.page_number == page_number), None
    )
    if page_meta and page_meta.classification == "image_only":
        return True

    anchor = PAGE_ANCHOR_TABLES.get(page_number)
    if anchor:
        anchor_table = next((t for t in doc_extraction.tables if t.table_id == anchor), None)
        if anchor_table is None:
            return False  # no anchor table and not image_only → page_missing, not our job
        return anchor_table.confidence < LOW_TABLE_CONFIDENCE

    page_tables = [t for t in doc_extraction.tables if t.page_number == page_number]
    if not page_tables:
        return True
    return all(t.confidence < LOW_TABLE_CONFIDENCE for t in page_tables)
