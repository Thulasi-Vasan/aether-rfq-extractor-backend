import hashlib
import json
from pathlib import Path
from shutil import copyfile

from app.core.config import Settings
from app.models import DocumentExtraction, ExcelFillReport
from app.services.errors import DocumentNotFoundError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def document_id_from_sha256(sha256: str) -> str:
    return sha256[:16]


class DocumentStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.settings.extractions_dir.mkdir(parents=True, exist_ok=True)
        self.settings.excel_outputs_dir.mkdir(parents=True, exist_ok=True)
        if self.settings.enable_debug_artifacts:
            self.settings.debug_dir.mkdir(parents=True, exist_ok=True)

    def upload_path(self, document_id: str) -> Path:
        return self.settings.uploads_dir / f"{document_id}.pdf"

    def extraction_path(self, document_id: str) -> Path:
        return self.settings.extractions_dir / f"{document_id}.json"

    def debug_path(self, document_id: str) -> Path:
        return self.settings.debug_dir / document_id

    def excel_output_dir(self, job_id: str) -> Path:
        return self.settings.excel_outputs_dir / job_id

    def excel_output_path(self, job_id: str) -> Path:
        return self.excel_output_dir(job_id) / "filled.xlsx"

    def excel_report_path(self, job_id: str) -> Path:
        return self.excel_output_dir(job_id) / "report.json"

    def has_extraction(self, document_id: str) -> bool:
        return self.extraction_path(document_id).exists()

    def save_upload(self, source_path: Path, document_id: str) -> Path:
        destination = self.upload_path(document_id)
        if source_path.resolve() != destination.resolve():
            copyfile(source_path, destination)
        return destination

    def save_extraction(self, extraction: DocumentExtraction) -> Path:
        path = self.extraction_path(extraction.document_id)
        path.write_text(
            extraction.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def load_extraction(self, document_id: str) -> DocumentExtraction:
        path = self.extraction_path(document_id)
        if not path.exists():
            raise DocumentNotFoundError(f"Document extraction '{document_id}' was not found.")
        return DocumentExtraction.model_validate_json(path.read_text(encoding="utf-8"))

    def save_excel_output(self, job_id: str, workbook_path: Path, report: ExcelFillReport) -> Path:
        output_dir = self.excel_output_dir(job_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.excel_output_path(job_id)
        if workbook_path.resolve() != destination.resolve():
            copyfile(workbook_path, destination)
        self.excel_report_path(job_id).write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def write_debug_json(self, document_id: str, name: str, payload: object) -> None:
        if not self.settings.enable_debug_artifacts:
            return
        debug_dir = self.debug_path(document_id)
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
