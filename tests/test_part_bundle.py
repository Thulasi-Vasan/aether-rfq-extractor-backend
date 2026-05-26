from __future__ import annotations

import importlib.util
from pathlib import Path

from app.core.config import Settings
from app.services.part_bundle import BundleInputFile, PartBundleExtractionService, part_bundle_id
from app.models import BundleFile
from app.services.storage import DocumentStore


REFERENCE_DIR = Path("docs/reference-docs")


def service() -> PartBundleExtractionService:
    return PartBundleExtractionService.__new__(PartBundleExtractionService)


def test_extracts_6503850_pdf_identity_and_specs() -> None:
    extractor = service()
    profile, relationships, warnings = extractor._extract_pdf(REFERENCE_DIR / "6503850_Rev_2 (4).pdf", "6503850_Rev_2 (4).pdf")

    assert not warnings
    assert profile is not None
    assert profile.part_number == "6503850"
    assert profile.revision == "2"
    assert profile.part_name == "HOUSING,COMPRESSOR"
    assert profile.stage == "CASTING"
    assert profile.drawing_category == "DETAIL"
    assert profile.state == "RELEASED"
    assert relationships == []
    assert [spec.spec_number for spec in profile.specifications] == ["E4-01-240"]


def test_extracts_6511292_pdf_bom_relationship() -> None:
    extractor = service()
    profile, relationships, warnings = extractor._extract_pdf(REFERENCE_DIR / "6511292_Rev_4 (3).pdf", "6511292_Rev_4 (3).pdf")

    assert not warnings
    assert profile is not None
    assert profile.part_number == "6511292"
    assert profile.revision == "4"
    assert profile.stage == "SEMI-FINISHED PART"
    assert len(relationships) == 1

    relationship = relationships[0]
    assert relationship.parent_part_number == "6511292"
    assert relationship.parent_stage == "SEMI-FINISHED PART"
    assert relationship.child_part_number == "6503850"
    assert relationship.child_name == "HOUSING,COMPRESSOR"
    assert relationship.quantity == 1
    assert relationship.unit_of_measure == "Each (ea)"
    assert relationship.method_of_use == "Standard"


def test_extracts_6543959_pdf_bom_and_multiple_specs() -> None:
    extractor = service()
    profile, relationships, warnings = extractor._extract_pdf(REFERENCE_DIR / "6543959_Rev_3 (2).pdf", "6543959_Rev_3 (2).pdf")

    assert not warnings
    assert profile is not None
    assert profile.part_number == "6543959"
    assert profile.revision == "3"
    assert profile.stage == "FINISHED PART"
    assert [spec.spec_number for spec in profile.specifications] == ["E4-01-179", "E4-01-249"]
    assert len(relationships) == 1
    assert relationships[0].parent_part_number == "6543959"
    assert relationships[0].child_part_number == "3798675"
    assert relationships[0].quantity == 1


def test_image_only_pdf_is_warned_without_ocr() -> None:
    extractor = service()
    profile, relationships, warnings = extractor._extract_pdf(REFERENCE_DIR / "3798675_1 (1).pdf", "3798675_1 (1).pdf")

    assert profile is None
    assert relationships == []
    assert [warning.code for warning in warnings] == ["image_only_pdf"]


def test_step_metadata_and_optional_geometry() -> None:
    extractor = service()

    for part_number in ("6503850", "6511292", "6543959"):
        geometry = extractor._extract_step(REFERENCE_DIR / f"{part_number}.stp", f"{part_number}.stp")
        assert geometry.step_product_number == part_number
        assert geometry.units == "mm"
        assert geometry.mass_kg is None

        if importlib.util.find_spec("OCC") is None and extractor._occ_worker_python() is None:
            assert [warning.code for warning in geometry.warnings] == ["cad_kernel_unavailable"]
        else:
            assert geometry.bounding_box_mm is not None
            assert geometry.bounding_box_mm.length > 0
            assert geometry.volume_mm3 is not None and geometry.volume_mm3 > 0
            assert geometry.surface_area_mm2 is not None and geometry.surface_area_mm2 > 0


def test_extract_bundle_merges_relationship_child_stage_when_profile_exists() -> None:
    extractor = service()
    files = [
        BundleInputFile(REFERENCE_DIR / "6511292_Rev_4 (3).pdf", "6511292_Rev_4 (3).pdf"),
        BundleInputFile(REFERENCE_DIR / "6503850_Rev_2 (4).pdf", "6503850_Rev_2 (4).pdf"),
        BundleInputFile(REFERENCE_DIR / "6511292.stp", "6511292.stp"),
        BundleInputFile(REFERENCE_DIR / "6503850.stp", "6503850.stp"),
    ]
    records = [
        BundleFile(filename=file.filename, sha256="0" * 64, file_type=extractor._file_type(file.filename))
        for file in files
    ]

    extraction = extractor.extract_bundle(files, bundle_id=part_bundle_id(records), file_records=records)

    parts = {part.part_number: part for part in extraction.parts}
    assert parts["6511292"].cad_geometry is not None
    assert parts["6503850"].cad_geometry is not None
    assert len(extraction.relationships) == 1
    assert extraction.relationships[0].child_stage == "CASTING"


def test_part_bundle_debug_text_artifacts_are_written(tmp_path: Path) -> None:
    settings = Settings(AETHER_DATA_DIR=tmp_path, AETHER_ENABLE_DEBUG_ARTIFACTS=True)
    store = DocumentStore(settings)
    extractor = PartBundleExtractionService(settings, store)
    files = [
        BundleInputFile(REFERENCE_DIR / "6511292_Rev_4 (3).pdf", "6511292_Rev_4 (3).pdf"),
        BundleInputFile(REFERENCE_DIR / "3798675_1 (1).pdf", "3798675_1 (1).pdf"),
    ]
    records = [
        BundleFile(filename=file.filename, sha256="0" * 64, file_type=extractor._file_type(file.filename))
        for file in files
    ]
    bundle_id = "debug-check"

    extractor.extract_bundle(files, bundle_id=bundle_id, file_records=records)

    debug_dir = settings.debug_dir / "part_bundles" / bundle_id
    vector_text = debug_dir / "6511292_Rev_4_3_text.txt"
    image_text = debug_dir / "3798675_1_1_text.txt"
    assert vector_text.exists()
    assert "PART NUMBER: 6511292" in vector_text.read_text(encoding="utf-8")
    assert image_text.exists()
    assert image_text.read_text(encoding="utf-8") == ""
