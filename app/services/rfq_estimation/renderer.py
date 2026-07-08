"""Render the 7-page RFQ Estimation report to PDF via WeasyPrint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.rfq_estimation.reference_data import default_context, deep_merge

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"
_TEMPLATE_NAME = "rfq_estimation.html.j2"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)


def _assign_group_spans(rows: list[dict[str, Any]]) -> None:
    """Set ``group_span`` on the first row of each rotated group section.

    Rows carry a ``group`` label only on the first row of a section; blank
    ``group`` continues the current section. We convert that into a rowspan the
    template renders as a single vertical label cell.
    """
    start = None
    for i, row in enumerate(rows):
        row.pop("group_span", None)
        if row.get("group"):
            if start is not None:
                rows[start]["group_span"] = i - start
            start = i
    if start is not None:
        rows[start]["group_span"] = len(rows) - start


def build_context(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge caller data onto the Meridian reference defaults and prep the context."""
    ctx = deep_merge(default_context(), overrides)
    _assign_group_spans(ctx["casting"]["capital_rows"])
    _assign_group_spans(ctx["casting"]["operating_rows"])
    return ctx


def render_estimation_html(overrides: dict[str, Any] | None = None) -> str:
    """Render the report to an HTML string (useful for debugging / preview)."""
    ctx = build_context(overrides)
    return _env.get_template(_TEMPLATE_NAME).render(**ctx)


def render_estimation_pdf(overrides: dict[str, Any] | None = None) -> bytes:
    """Render the full 7-page RFQ Estimation report to PDF bytes."""
    # Imported lazily so the module imports even if WeasyPrint's native libs
    # are unavailable in a given environment (keeps app startup resilient).
    from weasyprint import HTML

    html = render_estimation_html(overrides)
    return HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf()
