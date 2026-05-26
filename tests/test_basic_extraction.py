from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.models import BoundingBoxMm, CadGeometry, PartProfile, PartSpecification
from app.services.basic_extraction import BasicExtractionService, BasicInputFiles, MATERIAL_DENSITY_G_PER_CM3
from app.services.storage import DocumentStore


REFERENCE_DIR = Path("docs/reference-docs")


def test_basic_extraction_for_6511292_pair(tmp_path: Path) -> None:
    settings = Settings(AETHER_DATA_DIR=tmp_path, AETHER_ENABLE_DEBUG_ARTIFACTS=True)
    service = BasicExtractionService(settings, DocumentStore(settings))

    extraction = service.extract_basic(
        BasicInputFiles(
            pdf_path=REFERENCE_DIR / "6511292_Rev_4 (3).pdf",
            pdf_filename="6511292_Rev_4 (3).pdf",
            step_path=REFERENCE_DIR / "6511292.stp",
            step_filename="6511292.stp",
        ),
        extraction_id="basic-6511292",
    )

    assert extraction.part.final_part_no == "6511292"
    assert extraction.part.stage == "SEMI-FINISHED PART"
    assert extraction.material.spec_number == "E4-01-240"
    assert extraction.material.density_g_per_cm3 == 2.7
    assert extraction.bom.child_part_count == 1
    assert extraction.bom.children[0].part_number == "6503850"
    assert extraction.cad.step_product_number == "6511292"
    assert extraction.cad.volume_cm3 is not None
    assert extraction.mass.estimated_mass_kg is not None
    assert abs(extraction.mass.estimated_mass_kg - 2.965004) < 0.0001
    assert extraction.mass.declared_mass_kg is None
    assert extraction.viewer_files.pdf_url == "/v1/basic-extractions/basic-6511292/pdf"
    assert extraction.viewer_files.step_url == "/v1/basic-extractions/basic-6511292/step"
    assert (settings.debug_dir / "basic_extractions" / "basic-6511292" / "raw_text.txt").exists()
    assert (settings.debug_dir / "basic_extractions" / "basic-6511292" / "raw_blocks.json").exists()
    assert (settings.debug_dir / "basic_extractions" / "basic-6511292" / "raw_words.json").exists()


def test_basic_extraction_declared_casting_weight_implies_density(tmp_path: Path) -> None:
    settings = Settings(AETHER_DATA_DIR=tmp_path)
    service = BasicExtractionService(settings, DocumentStore(settings))

    extraction = service.extract_basic(
        BasicInputFiles(
            pdf_path=REFERENCE_DIR / "6503850_Rev_2 (4).pdf",
            pdf_filename="6503850_Rev_2 (4).pdf",
            step_path=REFERENCE_DIR / "6503850.stp",
            step_filename="6503850.stp",
        ),
        extraction_id="basic-6503850",
    )

    assert extraction.part.final_part_no == "6503850"
    assert extraction.part.stage == "CASTING"
    assert extraction.mass.declared_mass_kg == 3.8
    assert extraction.mass.implied_density_g_per_cm3 is not None
    assert abs(extraction.mass.implied_density_g_per_cm3 - 2.67636) < 0.0001


def test_basic_extraction_warns_on_pdf_step_part_mismatch(tmp_path: Path) -> None:
    settings = Settings(AETHER_DATA_DIR=tmp_path)
    service = BasicExtractionService(settings, DocumentStore(settings))

    extraction = service.extract_basic(
        BasicInputFiles(
            pdf_path=REFERENCE_DIR / "6511292_Rev_4 (3).pdf",
            pdf_filename="6511292_Rev_4 (3).pdf",
            step_path=REFERENCE_DIR / "6503850.stp",
            step_filename="6503850.stp",
        ),
        extraction_id="basic-mismatch",
    )

    assert "part_number_mismatch" in [warning.code for warning in extraction.warnings]


def test_basic_mass_stays_null_when_density_mapping_is_missing(tmp_path: Path) -> None:
    settings = Settings(AETHER_DATA_DIR=tmp_path)
    service = BasicExtractionService(settings, DocumentStore(settings))
    profile = PartProfile(
        part_number="1234567",
        specifications=[PartSpecification(spec_number="UNKNOWN", title="Unknown Material")],
    )
    warnings = []
    material = service._build_material(profile, warnings)
    cad = service._build_cad(
        CadGeometry(
            source_file="x.stp",
            step_product_number="1234567",
            units="mm",
            bounding_box_mm=BoundingBoxMm(
                x_min=0,
                y_min=0,
                z_min=0,
                x_max=10,
                y_max=10,
                z_max=10,
                length=10,
                width=10,
                height=10,
            ),
            volume_mm3=1000,
        )
    )

    mass = service._build_mass("", cad, material, warnings)

    assert material.density_g_per_cm3 is None
    assert mass.estimated_mass_kg is None
    assert [warning.code for warning in warnings] == ["density_mapping_missing", "mass_density_missing"]


def test_density_mapping_contains_current_reference_specs() -> None:
    assert MATERIAL_DENSITY_G_PER_CM3["E4-01-240"] == 2.7
    assert MATERIAL_DENSITY_G_PER_CM3["E4-01-179"] == 2.7
    assert MATERIAL_DENSITY_G_PER_CM3["E4-01-249"] == 2.7
