"""LLM-powered reasoning enrichment via AWS Bedrock.

Uses the Bedrock Converse API so the model_id is fully interchangeable —
swap AETHER_BEDROCK_MODEL_ID to any Bedrock-supported model without code changes.
"""
from __future__ import annotations

import json
import logging

import boto3

from app.models import FieldProvenance

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert at analysing RFQ (Request for Quotation) cost-estimation documents \
for die-casting manufacturing. You will be given a list of fields that were automatically \
populated into a cost sheet from a PDF document.

For each field, write ONE clear, concise sentence (max 20 words) explaining:
- where the value came from in the document (page, section, or table name if known), and
- what the field represents in plain business language.

Do NOT repeat the value itself in the reason.
Do NOT use technical jargon like "row_index" or "col_index".
Use natural language a non-technical manager can understand.
"""

_USER_TEMPLATE = """\
Document: {pdf_filename}

Fields to explain:
{fields_json}

Return a JSON array ONLY — no markdown fences, no explanation outside JSON.
Each element must have exactly two keys: "excel_cell" and "reason".
Example element: {{"excel_cell": "C2", "reason": "Taken from the RFQ header section on page 1."}}
"""


def _fields_to_prompt_payload(records: list[FieldProvenance]) -> str:
    items = []
    for r in records:
        item: dict = {
            "excel_cell": r.excel_cell,
            "label": r.label,
            "source_type": r.source_type,
        }
        if r.page_number is not None:
            item["page"] = r.page_number
        if r.source_type == "default":
            item["note"] = "hardcoded default — explain what it means for the cost sheet"
        elif r.source_type == "derived":
            item["note"] = "calculated/derived value — explain the derivation logic"
        items.append(item)
    return json.dumps(items, indent=2)


BATCH_SIZE = 30  # fields per Bedrock call — keeps each call under ~10s


class BedrockReasoningService:
    """Enriches FieldProvenance records with LLM-generated reasoning via Bedrock."""

    def __init__(self, model_id: str, region: str = "us-east-1") -> None:
        self.model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def enrich(self, records: list[FieldProvenance], pdf_filename: str) -> list[FieldProvenance]:
        """Return a new list of records with `reason` replaced by LLM-generated text.

        Fields with source_type "not_available" are skipped.
        Records are processed in batches of BATCH_SIZE to avoid large slow calls.
        """
        to_enrich = [r for r in records if r.source_type != "not_available"]
        skip = [r for r in records if r.source_type == "not_available"]

        if not to_enrich:
            return records

        reason_map: dict[str, str] = {}
        batches = [to_enrich[i:i + BATCH_SIZE] for i in range(0, len(to_enrich), BATCH_SIZE)]

        for batch in batches:
            prompt = _USER_TEMPLATE.format(
                pdf_filename=pdf_filename or "RFQ document",
                fields_json=_fields_to_prompt_payload(batch),
            )
            try:
                response = self._client.converse(
                    modelId=self.model_id,
                    system=[{"text": _SYSTEM_PROMPT}],
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": 2048, "temperature": 0.2},
                )
                raw = response["output"]["message"]["content"][0]["text"].strip()
                for item in self._parse_reasons(raw):
                    reason_map[item["excel_cell"]] = item["reason"]
            except Exception as exc:
                logger.warning("Bedrock batch failed (%d fields), skipping batch: %s", len(batch), exc)

        enriched = [
            r.model_copy(update={"reason": reason_map[r.excel_cell]})
            if r.excel_cell in reason_map
            else r
            for r in to_enrich
        ]
        return enriched + skip

    @staticmethod
    def _parse_reasons(raw: str) -> list[dict]:
        """Parse the JSON array from the model response robustly."""
        # Strip accidental markdown fences if model adds them
        text = raw
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, list):
                return [
                    item for item in parsed
                    if isinstance(item, dict) and "excel_cell" in item and "reason" in item
                ]
        except json.JSONDecodeError:
            logger.warning("Could not parse Bedrock response as JSON: %s", raw[:200])
        return []
