from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from fastapi import UploadFile

from app.core.config import Settings
from app.models import (
    BasicBomChild,
    BasicBomDetails,
    BasicCadDetails,
    BasicExtraction,
    BasicMassDetails,
    BasicMaterialDetails,
    BasicPartDetails,
    BasicSourceNote,
    BasicViewerFiles,
    ExtractionWarning,
    WarningSeverity,
)
from app.services.errors import InvalidBundleFileError
from app.services.part_bundle import PartBundleExtractionService
from app.services.storage import DocumentStore, sha256_file


MATERIAL_DENSITY_G_PER_CM3 = {
    "E4-01-240": 2.7,
    "E4-01-179": 2.7,
    "E4-01-249": 2.7,
}


@dataclass(frozen=True)
class BasicInputFiles:
    pdf_path: Path
    pdf_filename: str
    step_path: Path
    step_filename: str


def basic_extraction_id(pdf_sha256: str, step_sha256: str, pdf_filename: str, step_filename: str) -> str:
    digest = hashlib.sha256()
    for value in (pdf_filename.lower(), pdf_sha256, step_filename.lower(), step_sha256):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


class BasicExtractionService:
    def __init__(self, settings: Settings, store: DocumentStore) -> None:
        self.settings = settings
        self.store = store
        self.part_bundle = PartBundleExtractionService(settings, store)

    async def save_uploads_to_temp(self, pdf: UploadFile, step: UploadFile) -> BasicInputFiles:
        pdf_path = await self._save_upload_to_temp(pdf, expected="pdf")
        try:
            step_path = await self._save_upload_to_temp(step, expected="step")
        except Exception:
            pdf_path.unlink(missing_ok=True)
            raise
        return BasicInputFiles(
            pdf_path=pdf_path,
            pdf_filename=pdf.filename or "drawing.pdf",
            step_path=step_path,
            step_filename=step.filename or "model.stp",
        )

    def extract_uploads(
        self,
        files: BasicInputFiles,
        *,
        force_reextract: bool = False,
    ) -> tuple[BasicExtraction, bool]:
        pdf_sha = sha256_file(files.pdf_path)
        step_sha = sha256_file(files.step_path)
        extraction_id = basic_extraction_id(pdf_sha, step_sha, files.pdf_filename, files.step_filename)

        if self.store.has_basic_extraction(extraction_id) and not force_reextract:
            return self.store.load_basic_extraction(extraction_id), True

        extraction = self.extract_basic(files, extraction_id=extraction_id)
        self.store.save_basic_extraction(extraction, pdf_path=files.pdf_path, step_path=files.step_path)
        return extraction, False

    def extract_basic(self, files: BasicInputFiles, *, extraction_id: str) -> BasicExtraction:
        text, pdf_warnings = self._extract_pdf_debug_layer(files.pdf_path, files.pdf_filename, extraction_id)
        profile = None
        relationships = []
        warnings = list(pdf_warnings)
        if text.strip():
            profile = self.part_bundle._parse_pdf_profile(text, files.pdf_filename)
            if profile:
                relationships = self.part_bundle._parse_bom_relationships(
                    text,
                    profile.part_number,
                    profile.stage,
                    files.pdf_filename,
                )
            else:
                warnings.append(
                    ExtractionWarning(
                        code="part_number_missing",
                        message="PDF text was extracted, but no title-block part number was found.",
                        severity=WarningSeverity.warning,
                        details={"filename": files.pdf_filename},
                    )
                )

        geometry = self.part_bundle._extract_step(files.step_path, files.step_filename)
        warnings.extend(geometry.warnings)

        part = self._build_part(profile)
        material = self._build_material(profile, warnings)
        bom = self._build_bom(relationships)
        cad = self._build_cad(geometry)
        mass = self._build_mass(text, cad, material, warnings)
        sources = self._build_sources(files, profile, geometry, material, mass)

        if profile and geometry.step_product_number and profile.part_number != geometry.step_product_number:
            warnings.append(
                ExtractionWarning(
                    code="part_number_mismatch",
                    message="PDF title-block part number does not match STEP product number.",
                    severity=WarningSeverity.warning,
                    details={
                        "pdf_part_number": profile.part_number,
                        "step_product_number": geometry.step_product_number,
                    },
                )
            )

        return BasicExtraction(
            extraction_id=extraction_id,
            part=part,
            material=material,
            bom=bom,
            cad=cad,
            mass=mass,
            viewer_files=BasicViewerFiles(
                pdf_url=f"/v1/basic-extractions/{extraction_id}/pdf",
                step_url=f"/v1/basic-extractions/{extraction_id}/step",
            ),
            sources=sources,
            warnings=warnings,
        )

    async def _save_upload_to_temp(self, upload: UploadFile, *, expected: str) -> Path:
        filename = upload.filename or "upload"
        suffix = Path(filename).suffix.lower()
        if expected == "pdf" and suffix != ".pdf":
            raise InvalidBundleFileError("The pdf field must contain a PDF file.", details={"filename": filename})
        if expected == "step" and suffix not in {".stp", ".step"}:
            raise InvalidBundleFileError("The step field must contain a STEP file.", details={"filename": filename})

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        written = 0
        try:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > self.settings.max_upload_bytes:
                    raise InvalidBundleFileError(
                        "Uploaded file exceeds the configured size limit.",
                        details={"filename": filename, "max_upload_bytes": self.settings.max_upload_bytes},
                    )
                tmp.write(chunk)
        finally:
            tmp.close()

        if written == 0:
            tmp_path.unlink(missing_ok=True)
            raise InvalidBundleFileError("Uploaded file is empty.", details={"filename": filename})
        return tmp_path

    def _extract_pdf_debug_layer(
        self,
        path: Path,
        filename: str,
        extraction_id: str,
    ) -> tuple[str, list[ExtractionWarning]]:
        try:
            doc = fitz.open(path)
        except Exception as exc:
            return "", [
                ExtractionWarning(
                    code="pdf_read_failed",
                    message="PDF could not be read.",
                    severity=WarningSeverity.error,
                    details={"filename": filename, "reason": str(exc)},
                )
            ]

        try:
            page_texts = []
            blocks = []
            words = []
            for page_index, page in enumerate(doc, start=1):
                page_texts.append(page.get_text())
                blocks.append({"page_number": page_index, "blocks": page.get_text("blocks")})
                words.append({"page_number": page_index, "words": page.get_text("words")})
            text = "\n".join(page_texts)
        finally:
            doc.close()

        self.store.write_basic_debug_text(extraction_id, "raw_text.txt", text)
        self.store.write_basic_debug_json(extraction_id, "raw_blocks.json", blocks)
        self.store.write_basic_debug_json(extraction_id, "raw_words.json", words)

        if not text.strip():
            return text, [
                ExtractionWarning(
                    code="image_only_pdf",
                    message="PDF has no extractable vector text; OCR is deferred for basic extraction.",
                    severity=WarningSeverity.warning,
                    details={"filename": filename},
                )
            ]
        return text, []

    def _build_part(self, profile: object | None) -> BasicPartDetails:
        if profile is None:
            return BasicPartDetails()
        return BasicPartDetails(
            final_part_no=profile.part_number,
            part_number=profile.part_number,
            revision=profile.revision,
            part_name=profile.part_name,
            stage=profile.stage,
            drawing_category=profile.drawing_category,
            state=profile.state,
            project_name=None,
            company=None,
        )

    def _build_material(self, profile: object | None, warnings: list[ExtractionWarning]) -> BasicMaterialDetails:
        spec = profile.specifications[0] if profile and profile.specifications else None
        spec_number = spec.spec_number if spec else None
        density = MATERIAL_DENSITY_G_PER_CM3.get(spec_number or "")
        if spec_number and density is None:
            warnings.append(
                ExtractionWarning(
                    code="density_mapping_missing",
                    message="No internal density mapping is available for the extracted material specification.",
                    severity=WarningSeverity.warning,
                    details={"spec_number": spec_number},
                )
            )
        return BasicMaterialDetails(
            spec_number=spec_number,
            title=spec.title if spec else None,
            density_g_per_cm3=density,
            density_source="internal_spec_mapping" if density is not None else None,
        )

    def _build_bom(self, relationships: list[object]) -> BasicBomDetails:
        return BasicBomDetails(
            child_part_count=len(relationships),
            children=[
                BasicBomChild(
                    part_number=relationship.child_part_number,
                    name=relationship.child_name,
                    quantity=relationship.quantity,
                    unit_of_measure=relationship.unit_of_measure,
                    method_of_use=relationship.method_of_use,
                )
                for relationship in relationships
            ],
        )

    def _build_cad(self, geometry: object) -> BasicCadDetails:
        volume_cm3 = round(geometry.volume_mm3 / 1000, 6) if geometry.volume_mm3 is not None else None
        sorted_lbh = []
        if geometry.bounding_box_mm:
            sorted_lbh = sorted(
                [
                    geometry.bounding_box_mm.length,
                    geometry.bounding_box_mm.width,
                    geometry.bounding_box_mm.height,
                ],
                reverse=True,
            )
        return BasicCadDetails(
            step_product_number=geometry.step_product_number,
            units=geometry.units,
            bounding_box_mm=geometry.bounding_box_mm,
            sorted_lbh_mm=sorted_lbh,
            volume_mm3=geometry.volume_mm3,
            volume_cm3=volume_cm3,
            surface_area_mm2=geometry.surface_area_mm2,
            solid_count=geometry.solid_count,
        )

    def _build_mass(
        self,
        text: str,
        cad: BasicCadDetails,
        material: BasicMaterialDetails,
        warnings: list[ExtractionWarning],
    ) -> BasicMassDetails:
        declared = self._declared_mass_kg(text)
        estimated = None
        implied_density = None
        notes = []
        derivation = None

        if cad.volume_cm3 is not None and material.density_g_per_cm3 is not None:
            estimated = round(cad.volume_cm3 * material.density_g_per_cm3 / 1000, 6)
            derivation = "volume_cm3 * density_g_per_cm3 / 1000"
            notes.append("Estimated from STEP volume and internal material-spec density mapping.")
        elif cad.volume_cm3 is not None:
            warnings.append(
                ExtractionWarning(
                    code="mass_density_missing",
                    message="Mass could not be estimated because material density is unavailable.",
                    severity=WarningSeverity.warning,
                )
            )

        if declared is not None and cad.volume_cm3:
            implied_density = round((declared * 1000) / cad.volume_cm3, 6)
            notes.append("Implied density calculated from declared mass and STEP volume.")

        return BasicMassDetails(
            declared_mass_kg=declared,
            estimated_mass_kg=estimated,
            implied_density_g_per_cm3=implied_density,
            density_g_per_cm3=material.density_g_per_cm3,
            derivation=derivation,
            notes=notes,
        )

    def _declared_mass_kg(self, text: str) -> float | None:
        match = re.search(r"\bWEIGHT\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*kg\b", text, re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1))

    def _build_sources(
        self,
        files: BasicInputFiles,
        profile: object | None,
        geometry: object,
        material: BasicMaterialDetails,
        mass: BasicMassDetails,
    ) -> list[BasicSourceNote]:
        sources = [
            BasicSourceNote(
                field="cad",
                source_file=files.step_filename,
                source_type="step",
                note="CAD geometry was computed from the uploaded STEP file.",
            )
        ]
        if profile:
            sources.append(
                BasicSourceNote(
                    field="part",
                    source_file=files.pdf_filename,
                    source_type="pdf",
                    note="Part identity was parsed from the PDF title block text layer.",
                )
            )
            sources.append(
                BasicSourceNote(
                    field="bom",
                    source_file=files.pdf_filename,
                    source_type="pdf",
                    note="Child part count and child rows were derived from the Engineering Bill Of Material section.",
                )
            )
        if material.density_g_per_cm3 is not None:
            sources.append(
                BasicSourceNote(
                    field="material.density_g_per_cm3",
                    source_file=files.pdf_filename,
                    source_type="internal_mapping",
                    note=f"Density was mapped from material spec {material.spec_number}.",
                )
            )
        if mass.estimated_mass_kg is not None:
            sources.append(
                BasicSourceNote(
                    field="mass.estimated_mass_kg",
                    source_file=files.step_filename,
                    source_type="derived",
                    note="Mass was estimated from STEP volume and mapped material density.",
                )
            )
        _ = geometry
        return sources
