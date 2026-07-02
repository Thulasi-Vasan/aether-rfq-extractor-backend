import json

from app.models import FieldProvenance
from app.services.cost_estimation.reasoning import _fields_to_prompt_payload


def test_reasoning_payload_distinguishes_formula_and_formula_fallback():
    payload = json.loads(
        _fields_to_prompt_payload(
            [
                FieldProvenance(
                    excel_cell="N23",
                    field_key="core_shooting_total_cost",
                    label="Core Shooting M/c — Total Cost",
                    value="=(M23*L23)*V5",
                    source_type="formula",
                    reason="formula",
                ),
                FieldProvenance(
                    excel_cell="AD42",
                    field_key="cutting_tools_cost",
                    label="Cost of Cutting Tools",
                    value=3.63,
                    source_type="formula_fallback",
                    reason="fallback",
                ),
            ]
        )
    )

    assert payload[0]["source_type"] == "formula"
    assert "all required inputs were available" in payload[0]["note"]
    assert payload[1]["source_type"] == "formula_fallback"
    assert "directly extracted PDF value" in payload[1]["note"]
