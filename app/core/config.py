from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"), validation_alias="AETHER_DATA_DIR")
    reference_pdf_path: Path = Field(
        default=Path("samples/meridian-housing-gdc-reference.pdf"),
        validation_alias="AETHER_REFERENCE_PDF_PATH",
    )
    cors_origins: list[str] = Field(default=["*"], validation_alias="AETHER_CORS_ORIGINS")
    enable_debug_artifacts: bool = Field(
        default=False,
        validation_alias="AETHER_ENABLE_DEBUG_ARTIFACTS",
    )
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, validation_alias="AETHER_MAX_UPLOAD_BYTES")
    occ_python_path: Path | None = Field(default=None, validation_alias="AETHER_OCC_PYTHON")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def extractions_dir(self) -> Path:
        return self.data_dir / "extractions"

    @property
    def debug_dir(self) -> Path:
        return self.data_dir / "debug"

    @property
    def part_bundles_dir(self) -> Path:
        return self.data_dir / "part_bundles"


@lru_cache
def get_settings() -> Settings:
    return Settings()
