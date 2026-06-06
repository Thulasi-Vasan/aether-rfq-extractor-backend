import hashlib
import json
from pathlib import Path
from shutil import copyfile

from app.core.config import Settings
from app.models import DocumentExtraction, FieldProvenance
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
        if self.settings.enable_debug_artifacts:
            self.settings.debug_dir.mkdir(parents=True, exist_ok=True)

    def upload_path(self, document_id: str) -> Path:
        return self.settings.uploads_dir / f"{document_id}.pdf"

    def extraction_path(self, document_id: str) -> Path:
        return self.settings.extractions_dir / f"{document_id}.json"

    def debug_path(self, document_id: str) -> Path:
        return self.settings.debug_dir / document_id

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

    def provenance_path(self, document_id: str) -> Path:
        return self.settings.extractions_dir / f"{document_id}_provenance.json"

    def save_provenance(self, document_id: str, records: list[FieldProvenance]) -> Path:
        path = self.provenance_path(document_id)
        path.write_text(
            json.dumps([r.model_dump() for r in records], indent=2, default=str),
            encoding="utf-8",
        )
        return path

    def load_provenance(self, document_id: str) -> list[FieldProvenance] | None:
        path = self.provenance_path(document_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [FieldProvenance.model_validate(item) for item in raw]

    def write_debug_json(self, document_id: str, name: str, payload: object) -> None:
        if not self.settings.enable_debug_artifacts:
            return
        debug_dir = self.debug_path(document_id)
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
