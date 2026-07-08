import base64
import tempfile
from pathlib import Path

import fitz  # PyMuPDF


class CADRendererService:
    @staticmethod
    def render_step_to_base64_png(step_path: Path | str) -> str:
        """
        Renders a STEP file to a Base64-encoded PNG using cadquery and PyMuPDF.
        """
        # Imported lazily: cadquery pulls in a large native OCCT wheel that isn't
        # installed on every machine. Keeping it out of the module's top-level
        # imports means callers who never invoke this method (or who gate it
        # behind Settings.enable_cad_part_image) aren't forced to have it.
        import cadquery as cq

        # Load the STEP file
        shape = cq.importers.importStep(str(step_path))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = Path(tmpdir) / "render.svg"
            png_path = Path(tmpdir) / "render.png"
            
            # Export to SVG with cadquery
            cq.exporters.export(shape, str(svg_path))
            
            # Use PyMuPDF to convert SVG to PNG
            doc = fitz.open(svg_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=150)
            pix.save(str(png_path))
            
            # Read and encode PNG
            with open(png_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
