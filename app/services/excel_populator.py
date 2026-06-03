import io
import openpyxl

from app.core.config import Settings
from app.core.excel_mapping import EXCEL_MAPPING, set_cell_value
from app.models import MeridianExtractionResponse
from app.services.errors import ExtractorError


class ExcelExportService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def populate(self, extraction: MeridianExtractionResponse) -> bytes:
        template_path = self.settings.excel_template_path
        if not template_path.exists():
            raise ExtractorError(
                "Excel template not found.",
                status_code=404,
                details={"path": str(template_path)}
            )

        try:
            wb = openpyxl.load_workbook(template_path)
            if "Input Sheet" not in wb.sheetnames:
                raise ValueError("Sheet 'Input Sheet' not found in template.")
            sheet = wb["Input Sheet"]
            
            # Static mapping
            for coord, extractor_func in EXCEL_MAPPING.items():
                val = extractor_func(extraction)
                if val is not None:
                    set_cell_value(sheet, coord, val)
            
            # Strip images and comments to prevent exceljs parsing crash in frontend
            sheet._images = []
            if hasattr(sheet, '_drawings'):
                sheet._drawings = []
            sheet.legacy_drawing = None
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.comment:
                        cell.comment = None

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output.getvalue()
        except Exception as exc:
            raise ExtractorError("Failed to populate Excel template.", details={"reason": str(exc)}) from exc
