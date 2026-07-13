"""RFQ Estimation report — renders the 7-page neutral estimation PDF.

The report layout mirrors the established RFQ Estimation forms (Casting/GDC,
Machining, Process Planning, Assembly, Remarks, Packing). Neutral reference
data keeps sparse requests complete; callers deep-merge the stage data they
have onto those defaults.
"""

from app.services.rfq_estimation.renderer import render_estimation_pdf

__all__ = ["render_estimation_pdf"]
