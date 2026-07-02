import json
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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

    # AWS Bedrock - shared region, domain-specific models.
    bedrock_region: str = Field(default="us-east-1", validation_alias="AETHER_BEDROCK_REGION")
    cost_estimation_bedrock_model_id: str = Field(
        default="amazon.nova-lite-v1:0",
        validation_alias=AliasChoices("AETHER_COST_ESTIMATION_BEDROCK_MODEL_ID", "AETHER_BEDROCK_MODEL_ID"),
    )

    # Settings used only by the standalone machining-operation extractor.
    machining_bedrock_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        validation_alias=AliasChoices("AETHER_MACHINING_BEDROCK_MODEL_ID", "BEDROCK_MODEL_ID"),
    )
    machining_bedrock_max_tokens: int = Field(
        default=16384,
        validation_alias=AliasChoices("AETHER_MACHINING_BEDROCK_MAX_TOKENS", "BEDROCK_MAX_TOKENS"),
    )
    machining_bedrock_read_timeout_s: int = Field(
        default=300,
        validation_alias=AliasChoices("AETHER_MACHINING_BEDROCK_READ_TIMEOUT_S", "BEDROCK_READ_TIMEOUT_S"),
    )
    aws_profile: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AETHER_AWS_PROFILE", "AWS_PROFILE"),
    )
    material_density_g_per_mm3: float = Field(
        default=0.0027,
        validation_alias=AliasChoices("AETHER_MATERIAL_DENSITY_G_PER_MM3", "MATERIAL_DENSITY_G_PER_MM3"),
    )
    enable_occ: bool = Field(
        default=True,
        validation_alias=AliasChoices("AETHER_ENABLE_OCC", "ENABLE_OCC"),
    )
    use_static_summary: bool = Field(
        default=False,
        validation_alias=AliasChoices("AETHER_USE_STATIC_SUMMARY", "USE_STATIC_SUMMARY"),
    )
    static_step_summary: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AETHER_STATIC_STEP_SUMMARY", "STATIC_STEP_SUMMARY"),
    )

    def get_static_step_summary(self):
        """Parse STATIC_STEP_SUMMARY only when the static-summary path is used."""
        if self.static_step_summary is None or not self.static_step_summary.strip():
            return None

        from app.models import StepFeatureSummary

        try:
            raw_summary = json.loads(self.static_step_summary)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "STATIC_STEP_SUMMARY must be valid JSON matching StepFeatureSummary. "
                "Do not use placeholders like [...] or ..."
            ) from exc
        try:
            return StepFeatureSummary.model_validate(raw_summary)
        except ValueError as exc:
            raise ValueError("STATIC_STEP_SUMMARY does not match the StepFeatureSummary schema") from exc

    @property
    def bedrock_model_id(self) -> str:
        """Backward-compatible alias for the cost-estimation Bedrock model."""
        return self.cost_estimation_bedrock_model_id

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
