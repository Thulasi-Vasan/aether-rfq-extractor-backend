from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"), validation_alias="AETHER_DATA_DIR")
    reference_pdf_path: Path = Field(default=Path("samples/meridian-housing-gdc-reference.pdf"),validation_alias="AETHER_REFERENCE_PDF_PATH",)
    cors_origins: list[str] = Field(default=["*"], validation_alias="AETHER_CORS_ORIGINS")
    enable_debug_artifacts: bool = Field( default=False, validation_alias="AETHER_ENABLE_DEBUG_ARTIFACTS",)
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, validation_alias="AETHER_MAX_UPLOAD_BYTES")
    excel_target_fill_color: str = Field(default="FFFFFF00", validation_alias="AETHER_EXCEL_TARGET_FILL_COLOR")
    excel_template_path: Path = Field(default=Path("samples/Input Template.xlsx"), validation_alias="AETHER_EXCEL_TEMPLATE_PATH",)

    # AWS Bedrock — set these via env vars or .env file
    bedrock_region: str = Field(default="us-east-1", validation_alias="AETHER_BEDROCK_REGION")
    bedrock_model_id: str = Field(
        default="amazon.nova-lite-v1:0",
        validation_alias="AETHER_BEDROCK_MODEL_ID",
    )

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def extractions_dir(self) -> Path:
        return self.data_dir / "extractions"

    @property
    def debug_dir(self) -> Path:
        return self.data_dir / "debug"


@lru_cache
def get_settings() -> Settings:
    return Settings()
