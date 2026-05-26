from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from fastapi import UploadFile

from app.core.config import Settings
from app.models import (
    BomRelationship,
    BoundingBoxMm,
    BundleFile,
    CadGeometry,
    DrawingAuthorization,
    ExtractionWarning,
    PartBundleExtraction,
    PartProfile,
    PartSpecification,
    WarningSeverity,
)
from app.services.errors import InvalidBundleFileError
from app.services.storage import DocumentStore, sha256_file


STEP_PRODUCT_RE = re.compile(r"PRODUCT\('([^']+)'\s*,\s*'([^']*)'", re.IGNORECASE)
SPEC_NUMBER_RE = re.compile(r"^[A-Z]\d+(?:-[A-Z0-9]+)+$", re.IGNORECASE)
QUANTITY_RE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class BundleInputFile:
    path: Path
    filename: str
    content_type: str | None = None


def part_bundle_id(file_records: list[BundleFile]) -> str:
    digest = hashlib.sha256()
    for record in sorted(file_records, key=lambda item: (item.filename.lower(), item.sha256)):
        digest.update(record.filename.lower().encode("utf-8"))
        digest.update(b"\0")
        digest.update(record.sha256.encode("ascii"))
        digest.update(b"\0")
        digest.update(record.file_type.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\x00", "").splitlines() if line.strip()]


class PartBundleExtractionService:
    def __init__(self, settings: Settings, store: DocumentStore) -> None:
        self.settings = settings
        self.store = store

    async def save_uploads_to_temp(self, uploads: list[UploadFile]) -> list[BundleInputFile]:
        if not uploads:
            raise InvalidBundleFileError("At least one PDF or STEP file is required.")

        temp_files: list[BundleInputFile] = []
        try:
            for upload in uploads:
                filename = upload.filename or "upload"
                file_type = self._file_type(filename)
                suffix = ".pdf" if file_type == "pdf" else ".stp"
                written = 0
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp_path = Path(tmp.name)
                try:
                    while chunk := await upload.read(1024 * 1024):
                        written += len(chunk)
                        if written > self.settings.max_upload_bytes:
                            raise InvalidBundleFileError(
                                "Uploaded file exceeds the configured size limit.",
                                details={
                                    "filename": filename,
                                    "max_upload_bytes": self.settings.max_upload_bytes,
                                },
                            )
                        tmp.write(chunk)
                finally:
                    tmp.close()

                if written == 0:
                    tmp_path.unlink(missing_ok=True)
                    raise InvalidBundleFileError("Uploaded file is empty.", details={"filename": filename})
                temp_files.append(BundleInputFile(path=tmp_path, filename=filename, content_type=upload.content_type))
        except Exception:
            for temp_file in temp_files:
                temp_file.path.unlink(missing_ok=True)
            raise

        return temp_files

    def extract_uploads(
        self,
        files: list[BundleInputFile],
        *,
        force_reextract: bool = False,
    ) -> tuple[PartBundleExtraction, bool]:
        file_records = [
            BundleFile(
                filename=file.filename,
                sha256=sha256_file(file.path),
                file_type=self._file_type(file.filename),
            )
            for file in files
        ]
        bundle_id = part_bundle_id(file_records)

        if self.store.has_part_bundle(bundle_id) and not force_reextract:
            return self.store.load_part_bundle(bundle_id), True

        extraction = self.extract_bundle(files, bundle_id=bundle_id, file_records=file_records)
        self.store.save_part_bundle(extraction)
        return extraction, False

    def extract_bundle(
        self,
        files: list[BundleInputFile],
        *,
        bundle_id: str,
        file_records: list[BundleFile] | None = None,
    ) -> PartBundleExtraction:
        records = file_records or [
            BundleFile(
                filename=file.filename,
                sha256=sha256_file(file.path),
                file_type=self._file_type(file.filename),
            )
            for file in files
        ]
        records_by_name = {record.filename: record for record in records}

        parts: dict[str, PartProfile] = {}
        relationships: list[BomRelationship] = []
        warnings: list[ExtractionWarning] = []

        for file in files:
            record = records_by_name[file.filename]
            if record.file_type == "pdf":
                profile, file_relationships, file_warnings = self._extract_pdf(file.path, file.filename, bundle_id=bundle_id)
                record.warnings.extend(file_warnings)
                warnings.extend(file_warnings)
                if profile:
                    record.part_number = profile.part_number
                    self._merge_part(parts, profile)
                    relationships.extend(file_relationships)
                continue

            geometry = self._extract_step(file.path, file.filename)
            if geometry.step_product_number:
                record.part_number = geometry.step_product_number
                profile = parts.get(geometry.step_product_number) or PartProfile(
                    part_number=geometry.step_product_number,
                    source_files=[],
                )
                self._append_unique(profile.source_files, file.filename)
                profile.cad_geometry = geometry
                profile.warnings.extend(geometry.warnings)
                parts[profile.part_number] = profile
            record.warnings.extend(geometry.warnings)
            warnings.extend(geometry.warnings)

        self._resolve_relationship_children(relationships, parts, warnings)

        return PartBundleExtraction(
            bundle_id=bundle_id,
            files=records,
            parts=sorted(parts.values(), key=lambda part: part.part_number),
            relationships=relationships,
            warnings=warnings,
        )

    def _file_type(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".stp", ".step"}:
            return "step"
        raise InvalidBundleFileError(
            "Only PDF and STEP files are supported.",
            details={"filename": filename, "suffix": suffix},
        )

    def _extract_pdf(
        self,
        path: Path,
        filename: str,
        *,
        bundle_id: str | None = None,
    ) -> tuple[PartProfile | None, list[BomRelationship], list[ExtractionWarning]]:
        warnings: list[ExtractionWarning] = []
        try:
            doc = fitz.open(path)
        except Exception as exc:
            warning = ExtractionWarning(
                code="pdf_read_failed",
                message="PDF could not be read.",
                severity=WarningSeverity.error,
                details={"filename": filename, "reason": str(exc)},
            )
            return None, [], [warning]

        try:
            text = "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()

        if bundle_id is not None and hasattr(self, "store"):
            self.store.write_part_bundle_debug_text(bundle_id, self._debug_text_name(filename), text)

        if not text.strip():
            warning = ExtractionWarning(
                code="image_only_pdf",
                message="PDF has no extractable vector text; OCR is deferred for part-bundle extraction.",
                severity=WarningSeverity.warning,
                details={"filename": filename},
            )
            return None, [], [warning]

        profile = self._parse_pdf_profile(text, filename)
        if not profile:
            warning = ExtractionWarning(
                code="part_number_missing",
                message="PDF text was extracted, but no title-block part number was found.",
                severity=WarningSeverity.warning,
                details={"filename": filename},
            )
            return None, [], [warning]

        relationships = self._parse_bom_relationships(text, profile.part_number, profile.stage, filename)
        return profile, relationships, warnings

    def _debug_text_name(self, filename: str) -> str:
        stem = Path(filename).stem
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "pdf"
        return f"{safe}_text.txt"

    def _parse_pdf_profile(self, text: str, filename: str) -> PartProfile | None:
        part_number = self._field_value(text, "PART NUMBER") or self._mixed_field_value(text, "Part Number")
        if not part_number:
            return None

        profile = PartProfile(
            part_number=part_number,
            revision=self._field_value(text, "PART REVISION") or self._mixed_field_value(text, "Part Revision"),
            part_name=self._field_value(text, "PART NAME") or self._mixed_field_value(text, "Part Name"),
            stage=self._field_value(text, "ITEM IDENTIFIER"),
            drawing_category=self._field_value(text, "DRAWING CATEGORY"),
            state=self._field_value(text, "STATE"),
            company="Turbo Technologies" if "Turbo Technologies" in text else None,
            classification=self._classification(text),
            document_generated=self._document_generated(text),
            authorization=self._authorization(text),
            specifications=self._parse_specifications(text),
            source_files=[filename],
        )

        if profile.drawing_category and " State:" in profile.drawing_category:
            category, state = profile.drawing_category.split(" State:", 1)
            profile.drawing_category = category.strip()
            profile.state = profile.state or state.strip()

        return profile

    def _field_value(self, text: str, label: str) -> str | None:
        pattern = re.compile(rf"(?m)^{re.escape(label)}:\s*(?:\n\s*)?(.+?)\s*$")
        match = pattern.search(text)
        if not match:
            return None
        return match.group(1).strip() or None

    def _mixed_field_value(self, text: str, label: str) -> str | None:
        pattern = re.compile(rf"(?m)^{re.escape(label)}:\s*(.+?)\s*$", re.IGNORECASE)
        match = pattern.search(text)
        if not match:
            return None
        value = match.group(1).strip()
        if label.lower() == "part number":
            value = value.split()[0]
        return value or None

    def _classification(self, text: str) -> str | None:
        return (
            self._field_value(text, "CUMMINS DATA CLASSIFICATION")
            or self._mixed_multiline_value(text, "Cummins Data Classification")
        )

    def _document_generated(self, text: str) -> str | None:
        match = re.search(r"Document Generated:\s*(.+)", text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _mixed_multiline_value(self, text: str, label: str) -> str | None:
        pattern = re.compile(rf"(?im)^{re.escape(label)}:\s*(?:\n\s*)?(.+?)\s*$")
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    def _authorization(self, text: str) -> DrawingAuthorization | None:
        lines = clean_lines(text)
        authorization = DrawingAuthorization()
        authorization.drafter, authorization.drafter_date = self._person_and_date(lines, "Drafter")
        authorization.checker, authorization.checker_date = self._person_and_date(lines, "Checker")
        authorization.approver, authorization.approver_date = self._person_and_date(lines, "Approver")
        if authorization.model_dump(exclude_none=True):
            return authorization
        return None

    def _person_and_date(self, lines: list[str], label: str) -> tuple[str | None, str | None]:
        try:
            index = lines.index(label)
        except ValueError:
            return None, None
        person = lines[index + 1] if index + 1 < len(lines) else None
        date = None
        if index + 3 < len(lines) and lines[index + 2].lower() == "date":
            date = lines[index + 3]
        return person, date

    def _parse_bom_relationships(
        self,
        text: str,
        parent_part_number: str,
        parent_stage: str | None,
        filename: str,
    ) -> list[BomRelationship]:
        lines = self._section_lines(
            text,
            "Engineering Bill Of Material",
            ["Method of Use Definitions", "Associated Specifications", "Drawing Revision Information"],
        )
        if not lines:
            return []

        try:
            start = lines.index("Method of Use") + 1
        except ValueError:
            return []

        relationships: list[BomRelationship] = []
        index = start
        while index < len(lines):
            if lines[index] in {"Method of Use Definitions", "Associated Specifications"}:
                break
            if index + 2 >= len(lines):
                break

            find_no = lines[index]
            child_number = lines[index + 1]
            name_parts: list[str] = []
            cursor = index + 2
            while cursor < len(lines) and not QUANTITY_RE.fullmatch(lines[cursor]):
                name_parts.append(lines[cursor])
                cursor += 1

            if not name_parts or cursor + 2 >= len(lines):
                break

            relationships.append(
                BomRelationship(
                    parent_part_number=parent_part_number,
                    parent_stage=parent_stage,
                    child_part_number=child_number,
                    child_name=" ".join(name_parts),
                    quantity=self._parse_quantity(lines[cursor]),
                    unit_of_measure=lines[cursor + 1],
                    method_of_use=lines[cursor + 2],
                    source_file=filename,
                    warnings=[],
                )
            )
            _ = find_no
            index = cursor + 3

        return relationships

    def _parse_specifications(self, text: str) -> list[PartSpecification]:
        lines = self._section_lines(text, "Associated Specifications", ["Drawing Revision Information"])
        if not lines:
            return []

        try:
            start = lines.index("Sub-Category") + 1
        except ValueError:
            start = 0

        specs: list[PartSpecification] = []
        index = start
        while index < len(lines):
            if not SPEC_NUMBER_RE.fullmatch(lines[index]):
                index += 1
                continue

            spec_number = lines[index]
            index += 1
            title_parts: list[str] = []
            while index < len(lines) and not self._looks_like_spec_type(lines[index]):
                if SPEC_NUMBER_RE.fullmatch(lines[index]):
                    break
                title_parts.append(lines[index])
                index += 1

            spec_type = lines[index] if index < len(lines) and self._looks_like_spec_type(lines[index]) else None
            if spec_type:
                index += 1
            category = lines[index] if index < len(lines) else None
            if category:
                index += 1
            sub_category = lines[index] if index < len(lines) else None
            if sub_category:
                index += 1

            specs.append(
                PartSpecification(
                    spec_number=spec_number,
                    title=" ".join(title_parts) or None,
                    type=spec_type,
                    category=category,
                    sub_category=sub_category,
                )
            )

        return specs

    def _section_lines(self, text: str, start_marker: str, end_markers: list[str]) -> list[str]:
        start = text.find(start_marker)
        if start < 0:
            return []
        end_candidates = [text.find(marker, start + len(start_marker)) for marker in end_markers]
        end_candidates = [candidate for candidate in end_candidates if candidate >= 0]
        end = min(end_candidates) if end_candidates else len(text)
        return clean_lines(text[start:end])

    def _looks_like_spec_type(self, value: str) -> bool:
        return value.lower().endswith("specification")

    def _parse_quantity(self, value: str) -> int | float | str:
        if re.fullmatch(r"\d+", value):
            return int(value)
        if QUANTITY_RE.fullmatch(value):
            return float(value)
        return value

    def _extract_step(self, path: Path, filename: str) -> CadGeometry:
        text = path.read_text(encoding="utf-8", errors="ignore")
        product_number = self._step_product_number(text) or self._part_number_from_filename(filename)
        geometry = CadGeometry(
            source_file=filename,
            step_product_number=product_number,
            units=self._step_units(text),
            mass_kg=None,
        )
        self._compute_step_geometry(path, geometry)
        return geometry

    def _step_product_number(self, text: str) -> str | None:
        match = STEP_PRODUCT_RE.search(text)
        return match.group(1).strip() if match else None

    def _part_number_from_filename(self, filename: str) -> str | None:
        match = re.search(r"\d{6,}", filename)
        return match.group(0) if match else None

    def _step_units(self, text: str) -> str | None:
        if "SI_UNIT(.MILLI.,.METRE.)" in text:
            return "mm"
        if "SI_UNIT($,.METRE.)" in text or "SI_UNIT($, .METRE.)" in text:
            return "m"
        if "INCH" in text.upper():
            return "in"
        return None

    def _compute_step_geometry(self, path: Path, geometry: CadGeometry) -> None:
        if self._compute_step_geometry_in_process(path, geometry):
            return
        if self._compute_step_geometry_external(path, geometry):
            return

        geometry.warnings.append(
            ExtractionWarning(
                code="cad_kernel_unavailable",
                message="pythonocc-core is not installed; STEP geometry extraction was skipped.",
                severity=WarningSeverity.warning,
                details={"source_file": geometry.source_file},
            )
        )

    def _compute_step_geometry_in_process(self, path: Path, geometry: CadGeometry) -> bool:
        try:
            from OCC.Core.Bnd import Bnd_Box
            from OCC.Core.GProp import GProp_GProps
            from OCC.Core.IFSelect import IFSelect_RetDone
            from OCC.Core.STEPControl import STEPControl_Reader
            from OCC.Core.TopAbs import TopAbs_SOLID
            from OCC.Core.TopExp import TopExp_Explorer
        except ImportError:
            return False

        try:
            from OCC.Core.BRepBndLib import brepbndlib_Add as add_bounding_box
        except ImportError:
            from OCC.Core.BRepBndLib import brepbndlib

            add_bounding_box = brepbndlib.Add

        try:
            from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
        except ImportError:
            from OCC.Core.BRepGProp import brepgprop

            brepgprop_SurfaceProperties = brepgprop.SurfaceProperties
            brepgprop_VolumeProperties = brepgprop.VolumeProperties

        try:
            reader = STEPControl_Reader()
            status = reader.ReadFile(str(path))
            if status != IFSelect_RetDone:
                raise ValueError("OpenCascade could not read the STEP file.")
            reader.TransferRoots()
            shape = reader.OneShape()

            bbox = Bnd_Box()
            add_bounding_box(shape, bbox)
            x_min, y_min, z_min, x_max, y_max, z_max = bbox.Get()
            geometry.bounding_box_mm = BoundingBoxMm(
                x_min=round(float(x_min), 6),
                y_min=round(float(y_min), 6),
                z_min=round(float(z_min), 6),
                x_max=round(float(x_max), 6),
                y_max=round(float(y_max), 6),
                z_max=round(float(z_max), 6),
                length=round(float(x_max - x_min), 6),
                width=round(float(y_max - y_min), 6),
                height=round(float(z_max - z_min), 6),
            )

            volume_props = GProp_GProps()
            brepgprop_VolumeProperties(shape, volume_props)
            geometry.volume_mm3 = round(float(volume_props.Mass()), 6)

            surface_props = GProp_GProps()
            brepgprop_SurfaceProperties(shape, surface_props)
            geometry.surface_area_mm2 = round(float(surface_props.Mass()), 6)
            geometry.solid_count = self._solid_count(shape, TopExp_Explorer, TopAbs_SOLID)
        except Exception as exc:
            geometry.warnings.append(
                ExtractionWarning(
                    code="geometry_extraction_failed",
                    message="STEP geometry extraction failed.",
                    severity=WarningSeverity.warning,
                    details={"source_file": geometry.source_file, "reason": str(exc)},
                )
            )
        return True

    def _compute_step_geometry_external(self, path: Path, geometry: CadGeometry) -> bool:
        occ_python = self._occ_worker_python()
        if occ_python is None:
            return False

        worker = Path(__file__).with_name("occ_geometry_worker.py")
        completed = subprocess.run(
            [str(occ_python), str(worker), str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            reason = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            geometry.warnings.append(
                ExtractionWarning(
                    code="geometry_extraction_failed",
                    message="STEP geometry extraction failed.",
                    severity=WarningSeverity.warning,
                    details={
                        "source_file": geometry.source_file,
                        "worker_python": str(occ_python),
                        "reason": reason,
                    },
                )
            )
            return True

        try:
            payload = json.loads(completed.stdout)
            geometry.bounding_box_mm = BoundingBoxMm.model_validate(payload["bounding_box_mm"])
            geometry.volume_mm3 = payload.get("volume_mm3")
            geometry.surface_area_mm2 = payload.get("surface_area_mm2")
            geometry.solid_count = payload.get("solid_count")
        except Exception as exc:
            geometry.warnings.append(
                ExtractionWarning(
                    code="geometry_extraction_failed",
                    message="STEP geometry extraction worker returned invalid output.",
                    severity=WarningSeverity.warning,
                    details={
                        "source_file": geometry.source_file,
                        "worker_python": str(occ_python),
                        "reason": str(exc),
                    },
                )
            )
        return True

    def _occ_worker_python(self) -> Path | None:
        configured = self.settings.occ_python_path if hasattr(self, "settings") else None
        candidates: list[Path] = []
        if configured:
            candidates.append(configured)

        home = Path.home()
        candidates.extend(
            [
                home / "miniforge3" / "envs" / "cad-occ" / "bin" / "python",
                home / "miniconda3" / "envs" / "cad-occ" / "bin" / "python",
                home / "anaconda3" / "envs" / "cad-occ" / "bin" / "python",
            ]
        )

        for candidate in candidates:
            if candidate == Path(sys.executable) or not candidate.exists():
                continue
            if self._python_has_occ(candidate):
                return candidate
        return None

    def _python_has_occ(self, python_path: Path) -> bool:
        completed = subprocess.run(
            [str(python_path), "-c", "import OCC"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return completed.returncode == 0

    def _solid_count(self, shape: object, explorer_type: object, solid_type: object) -> int:
        explorer = explorer_type(shape, solid_type)
        count = 0
        while explorer.More():
            count += 1
            explorer.Next()
        return count

    def _merge_part(self, parts: dict[str, PartProfile], profile: PartProfile) -> None:
        existing = parts.get(profile.part_number)
        if not existing:
            parts[profile.part_number] = profile
            return

        for field in ("revision", "part_name", "stage", "drawing_category", "state", "company", "classification", "document_generated"):
            if getattr(existing, field) is None and getattr(profile, field) is not None:
                setattr(existing, field, getattr(profile, field))
        if existing.authorization is None:
            existing.authorization = profile.authorization
        for source_file in profile.source_files:
            self._append_unique(existing.source_files, source_file)
        for spec in profile.specifications:
            if spec.spec_number not in {existing_spec.spec_number for existing_spec in existing.specifications}:
                existing.specifications.append(spec)
        existing.warnings.extend(profile.warnings)

    def _resolve_relationship_children(
        self,
        relationships: list[BomRelationship],
        parts: dict[str, PartProfile],
        warnings: list[ExtractionWarning],
    ) -> None:
        for relationship in relationships:
            child = parts.get(relationship.child_part_number)
            if child:
                relationship.child_stage = child.stage
                continue

            warning = ExtractionWarning(
                code="child_profile_missing",
                message="BOM child part was referenced, but no parsed child profile is available in the bundle.",
                severity=WarningSeverity.warning,
                details={
                    "parent_part_number": relationship.parent_part_number,
                    "child_part_number": relationship.child_part_number,
                    "source_file": relationship.source_file,
                },
            )
            relationship.warnings.append(warning)
            warnings.append(warning)

    def _append_unique(self, values: list[str], value: str) -> None:
        if value not in values:
            values.append(value)
