"""RFQ Estimation report — renders the 7-page SCL-PED estimation PDF.

The report layout mirrors the SCL-PED "RFQ Estimation" forms (Casting/GDC,
Machining, Process Planning, Assembly, Remarks, Packing). The default context
in :mod:`reference_data` reproduces the Meridian Housing Compressor reference
sheet exactly; callers deep-merge the stage data they have onto those defaults.
"""

from app.services.rfq_estimation.renderer import render_estimation_pdf

__all__ = ["render_estimation_pdf"]
