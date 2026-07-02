"""Core agent: drawing PDF + STEP -> structured machining operations via Bedrock.

Uses the boto3 Bedrock Converse API:
  - the Rev-4 drawing is passed as a `document` block so the model can SEE it,
  - the STEP feature summary is passed as text,
  - a single forced tool (`record_machining_operations`) yields schema-validated
    structured output.
"""
from __future__ import annotations

import json
import logging
import re

from app.core.config import get_settings
from app.models import LLMResult, MachiningOperationsResponse, StepFeatureSummary
from .bedrock_client import get_bedrock_client
from .inventory import MACHINE_INVENTORY
from .pdf_locator import resolve_anchors
from .prompts import SYSTEM_PROMPT
from .step_parser import summarize_step, summary_to_prompt_text
from .tool_schema import TOOL_CONFIG, TOOL_NAME

log = logging.getLogger(__name__)

_DEGREE_FIX_RE = re.compile(r"(?<=\d)\s*\$")


class ExtractionError(RuntimeError):
    """Raised when the model does not return a usable tool call."""


def _clean_degree_text(text: str | None) -> str | None:
    """Render mangled degree symbols from the drawing text layer for display."""
    return _DEGREE_FIX_RE.sub("°", text) if text else text


def _clean_evidence_display_text(result: LLMResult) -> None:
    """Normalize user-facing evidence text without changing raw match_terms."""
    for op in result.operations:
        for ev in op.source_of_truth:
            try:
                ev.evidence_text = _clean_degree_text(ev.evidence_text)
                ev.verbatim_text = _clean_degree_text(ev.verbatim_text)
            except Exception:  # noqa: BLE001 - one evidence item must not break extraction
                log.debug("Could not clean degree text for opn %s evidence", op.opn_no, exc_info=True)


def _validate_inventory_names(result: LLMResult) -> None:
    """Log off-list inventory selections and snap simple casing/spacing near-matches."""
    if not MACHINE_INVENTORY:
        return
    allowed = {machine.strip().casefold(): machine for machine in MACHINE_INVENTORY}
    for op in result.operations:
        canonical = allowed.get(op.operation_name.strip().casefold())
        if canonical is None:
            log.warning("opn %s: operation_name %r not in inventory", op.opn_no, op.operation_name)
        elif canonical != op.operation_name:
            log.warning("opn %s: normalized operation_name %r to %r", op.opn_no, op.operation_name, canonical)
            op.operation_name = canonical


def _extract_tool_input(response: dict) -> dict:
    """Pull the forced tool's JSON input out of a Converse response."""
    content = response.get("output", {}).get("message", {}).get("content", [])
    for block in content:
        tool_use = block.get("toolUse")
        if tool_use and tool_use.get("name") == TOOL_NAME:
            return tool_use.get("input", {})
    stop_reason = response.get("stopReason")
    raise ExtractionError(
        f"Model did not call {TOOL_NAME!r} (stopReason={stop_reason!r}). "
        f"Raw content: {json.dumps(content)[:500]}"
    )


def _call_bedrock(pdf_bytes: bytes, step_summary: StepFeatureSummary | None) -> dict:
    settings = get_settings()
    client = get_bedrock_client()

    step_context = ("\n\n" + summary_to_prompt_text(step_summary)) if step_summary is not None else ""
    user_text = (
        "Determine the ordered machining operations for this part."
        + step_context
        + "\nThe attached PDF is the 2D engineering drawing."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "document": {
                        "format": "pdf",
                        # Converse document names: alphanumerics/space/hyphen only.
                        "name": "engineering drawing",
                        "source": {"bytes": pdf_bytes},
                    }
                },
                {"text": user_text},
            ],
        }
    ]

    log.info("Bedrock: calling model=%s  pdf=%d KB", settings.machining_bedrock_model_id, len(pdf_bytes) // 1024)
    response = client.converse(
        modelId=settings.machining_bedrock_model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        toolConfig=TOOL_CONFIG,
        inferenceConfig={"maxTokens": settings.machining_bedrock_max_tokens},
    )
    usage = response.get("usage", {})
    log.info(
        "Bedrock: done  input_tokens=%s  output_tokens=%s  stop=%s",
        usage.get("inputTokens", "?"),
        usage.get("outputTokens", "?"),
        response.get("stopReason", "?"),
    )
    return response


def extract_operations(pdf_bytes: bytes, step_path: str) -> MachiningOperationsResponse:
    """Run the full pipeline and return the frontend-ready response."""
    settings = get_settings()

    if settings.enable_occ:
        step_summary = summarize_step(step_path, settings.material_density_g_per_mm3)
        log.info("STEP summary JSON (copy this as STATIC_STEP_SUMMARY in .env):\n%s", step_summary.model_dump_json())
    elif settings.use_static_summary:
        step_summary = settings.get_static_step_summary()
        if step_summary is None:
            raise ValueError("USE_STATIC_SUMMARY=true but STATIC_STEP_SUMMARY is not set in .env")
        log.info("OCC disabled: using static STEP summary from env")
    else:
        step_summary = None
        log.info("OCC disabled and USE_STATIC_SUMMARY=false: sending no STEP context to LLM")

    response = _call_bedrock(pdf_bytes, step_summary)

    tool_input = _extract_tool_input(response)
    llm_result = LLMResult.model_validate(tool_input)
    _clean_evidence_display_text(llm_result)
    _validate_inventory_names(llm_result)

    # Keep operations in process order regardless of model ordering.
    ops = sorted(llm_result.operations, key=lambda o: o.opn_no)
    part_number = llm_result.part_overview.part_number
    log.info("LLM: part_number=%r  operations=%d", part_number, len(ops))
    for op in ops:
        log.info("  opn %d — %s", op.opn_no, op.operation_name)

    # Resolve each evidence item to a PDF page + bbox (backend is the coord authority).
    resolve_anchors(pdf_bytes, ops)

    return MachiningOperationsResponse(
        part_overview=llm_result.part_overview,
        part_number=part_number,
        model_id=settings.machining_bedrock_model_id,
        operations=ops,
        step_features=step_summary,
    )
