from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.documents.extractor import PdfExtractionService
from app.services.storage import DocumentStore


def get_store(settings: Settings = Depends(get_settings)) -> DocumentStore:
    return DocumentStore(settings)


def get_extractor(
    settings: Settings = Depends(get_settings),
    store: DocumentStore = Depends(get_store),
) -> PdfExtractionService:
    return PdfExtractionService(settings, store)


def get_excel_exporter(settings: Settings = Depends(get_settings)) -> ExcelExportService:
    return ExcelExportService(settings)
