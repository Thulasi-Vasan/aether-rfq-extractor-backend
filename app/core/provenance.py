from __future__ import annotations

from app.models import FieldProvenance


class ProvenanceRecorder:
    def __init__(self) -> None:
        self._records: dict[str, FieldProvenance] = {}

    def record(self, provenance: FieldProvenance) -> None:
        self._records[provenance.excel_cell] = provenance

    def get(self, excel_cell: str) -> FieldProvenance | None:
        return self._records.get(excel_cell)

    def get_all(self) -> list[FieldProvenance]:
        return list(self._records.values())
