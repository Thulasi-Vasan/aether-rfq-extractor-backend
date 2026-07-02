"""JSON schema for the forced Bedrock Converse tool.

Forcing a single tool (`toolChoice = {tool: ...}`) is how we get reliable,
schema-validated structured output out of the model. The schema mirrors the
process-plan structure the system prompt produces: a part overview and an ordered
list of richly-described operations.

Design notes:
  - Overview fields are nullable so the model never hallucinates to fill an
    unreadable title-block field — it leaves it null when unavailable.
  - `source_of_truth` is STRUCTURED (a list of evidence items) so the frontend
    can render and a reviewer can verify each drawing citation.
  - Per-operation justification is split into `why_machine_process` and
    `sequence_rationale`, matching the prompt's Justification bullet structure.
  - The drawing is the sole source of truth for operation decisions; the STEP
    summary supports geometry understanding only and must never be cited as
    drawing evidence (enforced in the prompt, restated here for the model).
"""

from .inventory import MACHINE_INVENTORY

TOOL_NAME = "record_machining_operations"

_INVENTORY_NAME_DESCRIPTION = (
    "MUST be chosen EXACTLY from the fixed machine/work-center inventory list — "
    "do not invent or reword. Pick based on the operation and the part's size/features."
)

_OPERATION_NAME_SCHEMA = {
    "type": "string",
    "description": (
        "The operation/work-center name shown in the response. " + _INVENTORY_NAME_DESCRIPTION
    ),
}
if MACHINE_INVENTORY:
    _OPERATION_NAME_SCHEMA["enum"] = MACHINE_INVENTORY

_EVIDENCE_ITEM = {
    "type": "object",
    "description": "A single piece of drawing evidence justifying the operation.",
    "properties": {
        "evidence_text": {
            "type": "string",
            "description": (
                "The exact drawing evidence, e.g. 'Ø124.55-124.60' or "
                "'NOTE: Slot into volute shall be completed prior to finish machining'."
            ),
        },
        "evidence_type": {
            "type": "string",
            "enum": ["dimension", "note", "spec", "datum", "classification", "view_ref"],
            "description": "What kind of drawing evidence this is.",
        },
        "verbatim_text": {
            "type": ["string", "null"],
            "description": (
                "The single MOST DISTINCTIVE exact token as printed on the drawing, used "
                "to anchor the highlight — prefer a unique dimension/spec value like "
                "'65.15' or 'E4-05-047', NOT a common word like 'GAUGE'. Null if none."
            ),
        },
        "match_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Up to 5 exact tokens printed on the drawing for this evidence, MOST "
                "DISTINCTIVE FIRST (e.g. ['65.15','64.85','GAUGE']). Literal tokens copied "
                "from the sheet only — no paraphrasing or added words. Used to locate and "
                "disambiguate the evidence on the PDF."
            ),
        },
        "sheet": {
            "type": ["string", "null"],
            "description": "Sheet the evidence appears on, e.g. 'Sheet 1'. Null if unknown.",
        },
        "view_or_detail": {
            "type": ["string", "null"],
            "description": (
                "Actual drawing view/detail that contains the evidence token, not simply the "
                "nearest printed label. If inside an enlarged detail, use that detail as the "
                "primary reference, e.g. 'Detail AC 5:1 / Section Z-Z'. Use null if unknown."
            ),
        },
    },
    "required": ["evidence_text", "evidence_type", "verbatim_text", "match_terms"],
}

_PART_OVERVIEW = {
    "type": "object",
    "description": "High-level overview of the part, read from the drawing title block / notes.",
    "properties": {
        "part_name": {"type": ["string", "null"], "description": "Part name from the title block."},
        "part_number": {"type": ["string", "null"], "description": "Part number from the title block."},
        "revision": {"type": ["string", "null"], "description": "Drawing revision."},
        "input_blank": {
            "type": ["string", "null"],
            "description": "Input blank type (casting vs semi-finished), from Item Identifier / BOM.",
        },
        "material": {
            "type": ["string", "null"],
            "description": "Material, from the Associated Specifications.",
        },
        "drawing_standard": {
            "type": ["string", "null"],
            "description": "Governing drawing standard from the title block, e.g. 'ASME Y14.5-2009'.",
        },
    },
    "required": [
        "part_name",
        "part_number",
        "revision",
        "input_blank",
        "material",
        "drawing_standard",
    ],
}

_OPERATION = {
    "type": "object",
    "properties": {
        "opn_no": {
            "type": "integer",
            "description": "Operation number in process order (e.g. 20, 30, 40 ...).",
        },
        "operation_name": _OPERATION_NAME_SCHEMA,
        "operation_description": {
            "type": "string",
            "description": (
                "One plain-language sentence describing the actual work done in this "
                "operation, e.g. rough bore inducer, finish machine diffuser face, "
                "wash, leak test, or final inspection."
            ),
        },
        "why_machine_process": {
            "type": "string",
            "description": (
                "Which inventory machine/process applies and why — tie to specific drawing "
                "evidence (dimension, note, or classification) that justifies this choice."
            ),
        },
        "sequence_rationale": {
            "type": "string",
            "description": (
                "Why this operation appears at this point in the sequence — what came before "
                "that makes it possible, and any drawing note/flag/spec that mandates the order."
            ),
        },
        "source_of_truth": {
            "type": "array",
            "description": (
                "Drawing evidence ONLY (never STEP geometry) that justifies this operation."
            ),
            "items": _EVIDENCE_ITEM,
        },
    },
    "required": [
        "opn_no",
        "operation_name",
        "operation_description",
        "why_machine_process",
        "sequence_rationale",
        "source_of_truth",
    ],
}

TOOL_SPEC = {
    "toolSpec": {
        "name": TOOL_NAME,
        "description": (
            "Record the complete machining process plan interpreted from the 2D "
            "engineering drawing (sole source of truth) and supported by the 3D STEP "
            "geometry summary. Operations must be in process order (lowest number first)."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "part_overview": _PART_OVERVIEW,
                    "operations": {
                        "type": "array",
                        "description": "Ordered machining operations.",
                        "items": _OPERATION,
                    },
                },
                "required": ["part_overview", "operations"],
            }
        },
    }
}

TOOL_CONFIG = {
    "tools": [TOOL_SPEC],
    "toolChoice": {"tool": {"name": TOOL_NAME}},
}
