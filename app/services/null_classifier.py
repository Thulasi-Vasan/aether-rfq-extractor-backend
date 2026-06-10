from __future__ import annotations

from app.core.excel_mapping import (
    BLOCKING_CATEGORIES,
    CELL_PAGE,
    CELL_PAGE_TYPE,
    DERIVED_DEPENDENCIES,
    PAGE_ANCHOR_TABLES,
    PAGE_CONTENT_FIELD,
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

    # Check page presence using structured page_type — content-aware, survives renumbering.
    if not _page_content_present(page_number, structured, doc_extraction):
        return "page_missing"

    if _page_unparseable(page_number, doc_extraction):
        return "extraction_failure"

    return "data_absent"


def blocks_approval(category: NullCategory) -> bool:
    return category in BLOCKING_CATEGORIES


def _page_content_present(
    page_number: int,
    structured: MeridianExtractionResponse,
    doc_extraction: DocumentExtraction,
) -> bool:
    """Check that the expected content for this page actually exists.

    Primary check: look for the expected page_type in the structured JSON output.
    This is content-aware and survives PDF page renumbering — if page 3 is removed,
    the structured JSON will have no page with page_type='machining_estimation'.

    Fallback for pages without a known page_type (e.g. pages 2, 4, 6): check
    physical page presence in doc_extraction, with image_only treated as present.
    """
    page_type = CELL_PAGE_TYPE.get(page_number)
    if page_type:
        page = next(
            (p for p in structured.pages if getattr(p, "page_type", "") == page_type),
            None,
        )
        if page is None:
            return False
        # Check the page-specific content field (not the header — header fields like
        # rfq_no and customer appear on every page and leak across when pages renumber).
        content_field = PAGE_CONTENT_FIELD.get(page_type)
        if content_field:
            value = getattr(page, content_field, None)
            has_content = (
                (isinstance(value, list) and len(value) > 0)
                or (not isinstance(value, list) and value not in (None, {}, ""))
            )
            if has_content:
                return True
            # Content is empty — could be page_missing OR extraction_failure (image-only
            # page that couldn't be parsed). Check physical page metadata as tiebreaker.
            page_meta = next(
                (p for p in doc_extraction.pages if p.page_number == page_number), None
            )
            if page_meta and page_meta.classification == "image_only":
                return True  # physically present but unparseable → extraction_failure
            return False
        return True  # no content field defined — treat as present

    # Fallback: physical page presence (for pages 2, 4, 6 which have no page_type key).
    page_meta = next(
        (p for p in doc_extraction.pages if p.page_number == page_number), None
    )
    if page_meta and page_meta.classification == "image_only":
        return True  # present but image-only → extraction_failure, not page_missing
    return page_meta is not None


def _page_unparseable(page_number: int, doc_extraction: DocumentExtraction) -> bool:
    # Check page metadata for image_only classification.
    page_meta = next(
        (p for p in doc_extraction.pages if p.page_number == page_number), None
    )
    if page_meta and page_meta.classification == "image_only":
        return True

    anchor = PAGE_ANCHOR_TABLES.get(page_number)
    if anchor:
        anchor_table = next((t for t in doc_extraction.tables if t.table_id == anchor), None)
        if anchor_table is None:
            return False  # anchor missing but not image_only → page_missing handles it
        return anchor_table.confidence < LOW_TABLE_CONFIDENCE

    page_tables = [t for t in doc_extraction.tables if t.page_number == page_number]
    if not page_tables:
        return True
    return all(t.confidence < LOW_TABLE_CONFIDENCE for t in page_tables)
