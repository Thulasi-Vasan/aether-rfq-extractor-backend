"""Neutral default context for the RFQ Estimation demo report.

The renderer deep-merges caller-supplied stage data onto a fresh copy of this
context, so omitted fields still produce a complete report without exposing
customer or company-specific reference data.
"""

from __future__ import annotations

import copy
from typing import Any


def _header() -> dict[str, Any]:
    return {
        "rfq_no": "RFQ-783214",
        "customer": "Creston Mobility",
        "final_part_no": "742681",
        "final_part_rev": "3",
        "description": "Compressor Housing Cover",
        "alloy": "E4-01-240 (C355-T71)",
        "alternate_alloy": "-",
        "date": "2026-07-10",
        "annual_volume": "33,000",
        "annual_volume_incl_rejection": "37,950",
        "machined_part_wt": "2.960",
        "casting_weight": "3.800",
        "lbh": "242 x211 x134",
        "takt_time": "8.00",
        # Optional data-URI (e.g. "data:image/png;base64,...") for the part
        # render shown on the Casting / Process Planning / Packing pages.
        "part_image": None,
    }


def _casting() -> dict[str, Any]:
    return {
        "title": "RFQ ESTIMATION FOR GRAVITY DIE CASTING (GDC)",
        "form_ref": "",
        "addl_info": "",
        # Left "Output/ m/c details" table.
        "output_rows": [
            {"name": "Sand core 1", "cavities": "2", "cycle": "5.0", "output": "24"},
            {"name": "Sand core 2", "cavities": "", "cycle": "", "output": "0"},
            {"name": "Sand core 3", "cavities": "", "cycle": "", "output": "0"},
            {"name": "Sand core 4", "cavities": "", "cycle": "", "output": "0"},
            {"name": "Decore", "cavities": "1", "cycle": "2.0", "output": "30"},
            {"name": "Casting", "cavities": "2", "cycle": "6.0", "output": "20"},
            {"name": "Cutting 1", "cavities": "1", "cycle": "2.0", "output": "30"},
            {"name": "Cutting 2", "cavities": "", "cycle": "", "output": "0"},
            {"name": "Linishing", "cavities": "1", "cycle": "2.0", "output": "30"},
            {"name": "Shot blasting", "cavities": "", "cycle": "", "output": "192"},
        ],
        # Right-hand parameter block beside the output table.
        "params": {
            "casting_category": "Medium-Hor",
            "cells_planned": "1",
            "sand_core_wt": "2.75",
            "man_power": "6",
            "floor_space": "676",
            "shot_blasting_type": "Hanger Type",
            "surface_coating": "-",
        },
        # Left "Capital Investments (Rs. Lac)" table. `group` labels the rotated
        # section header; blank group continues the previous section.
        "capital_rows": [
            {"group": "Sand core", "name": "Core shooting M/c -1", "util": "32%", "units": "1", "amount_cell": "45.0", "total": "45.0", "hl": True},
            {"group": "", "name": "Core shooting M/c -2", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Core Painting Oven (if any)", "util": "", "units": "0", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Thermal Decoring M/c", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Vibro Decoring Machine", "util": "25%", "units": "1", "amount_cell": "20.0", "total": "20.0"},
            {"group": "Casting", "name": "Tilting Machine", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Vertical Machine", "util": "38%", "units": "1", "amount_cell": "25.0", "total": "25.0"},
            {"group": "", "name": "Stand type Machine", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Hydraulic Power Pack", "util": "", "units": "", "amount_cell": "5.0", "total": "5.0"},
            {"group": "", "name": "Holding furnace", "util": "", "units": "2", "amount_cell": "14.0", "total": "28.0"},
            {"group": "Post casting", "name": "Band saw machine", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Circular saw cutting machine", "util": "25%", "units": "1", "amount_cell": "60.0", "total": "60.0"},
            {"group": "", "name": "Riser cutting machine", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "", "name": "Knock out Press", "util": "", "units": "1", "amount_cell": "3.5", "total": "3.5"},
            {"group": "", "name": "Linishing Machine with Dust Extractor", "util": "25%", "units": "1", "amount_cell": "2.2", "total": "2.2"},
            {"group": "", "name": "Shift code punching Machine", "util": "", "units": "1", "amount_cell": "3.0", "total": "3.0"},
            {"group": "", "name": "Welding Machine", "util": "", "units": "0", "amount_cell": "0.0", "total": "0.0"},
            {"group": "", "name": "Bend Removal Press", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "Automation", "name": "Auto Laddle", "util": "", "units": "1", "amount_cell": "0.0", "total": "0.0"},
            {"group": "", "name": "Robot Pouring & Extraction", "util": "", "units": "1", "amount_cell": "60.0", "total": "60.0"},
            {"group": "", "name": "Robot cell (Pouring robot, Quenching, Cutting m/c, cell forming)", "util": "", "units": "0", "amount_cell": "0.0", "total": "0.0"},
            {"group": "", "name": "Component Extractor or Catcher", "util": "", "units": "1", "amount_cell": "0.0", "total": "0.0"},
            {"group": "Others", "name": "Endoscope", "util": "", "units": "1", "amount_cell": "8.0", "total": "8.0"},
            {"group": "", "name": "Special Core handling / Testing", "util": "", "units": "1", "amount_cell": "12.0", "total": "12.0", "hl": True},
            {"group": "", "name": "Auto Air cleaning", "util": "", "units": "", "amount_cell": "", "total": "0.0"},
            {"group": "Common Facilities", "name": "Shot blasting M/c", "util": "4%", "units": "", "amount_cell": "Refer Note", "total": "0.0"},
            {"group": "", "name": "Melting furnace", "util": "1%", "units": "1", "amount_cell": "80.6", "total": "80.6"},
            {"group": "", "name": "Melting furnace accessories (Fork lift, ATL, Degassing unit, Dross trolley, scrubber unit)", "util": "", "units": "", "amount_cell": "37.0", "total": "37.0"},
            {"group": "", "name": "Heat Treatment Furnace (incl crane)", "util": "", "units": "", "amount_cell": "Refer Note", "total": ""},
            {"group": "", "name": "Heat Treatment BatchCode Punching M/c", "util": "", "units": "1", "amount_cell": "6.0", "total": "6.0"},
            {"group": "", "name": "Core placement fixture", "util": "", "units": "1", "amount_cell": "2.0", "total": "2.0"},
        ],
        "total_investment": "397.3",
        "die": {
            "no_of_dies": "1",
            "die_life": "50,000",
            "corebox_life": "50,000",
        },
        # Right "Operating Cost (Rs. Lac)" table.
        "operating_rows": [
            {"group": "Sand core", "name": "Dressing Station", "amount": "0.4", "hl": True},
            {"group": "", "name": "Core Painting Station", "amount": "0.8", "hl": True},
            {"group": "", "name": "Core Handling Stand", "amount": "1.2", "hl": True},
            {"group": "", "name": "Core Cavity  Handling Trolleys", "amount": "2.4", "hl": True},
            {"group": "", "name": "Core visual inspection / Table / tools", "amount": "0.8", "hl": True},
            {"group": "Casting", "name": "Vibro Decoring Hammer", "amount": "1.0"},
            {"group": "", "name": "Vibro Decoring Fixture", "amount": "0.8"},
            {"group": "", "name": "Casting Table", "amount": "0.3"},
            {"group": "", "name": "Casting & Sand collection Trolley", "amount": "0.3"},
            {"group": "", "name": "Furnace Dross, Rejection trolley & Ladle set", "amount": "0.5"},
            {"group": "Post Casting", "name": "Cutting Fixture (Circular/ Riser/ Band)", "amount": "0.8"},
            {"group": "", "name": "Riser Collection Trolley", "amount": "1.5"},
            {"group": "", "name": "Fettling table with Indexing Head", "amount": "0.8"},
            {"group": "", "name": "Indexing Fixture", "amount": "0.3"},
            {"group": "", "name": "Fettling Table", "amount": "0.3"},
            {"group": "", "name": "Fettling Booth", "amount": "0.5"},
            {"group": "", "name": "Cell Formation Cost", "amount": "-"},
            {"group": "", "name": "Filing & Grinding Tools", "amount": "0.5"},
            {"group": "", "name": "Final Inspection Table (Post cast+ HT)", "amount": "0.3"},
            {"group": "", "name": "Storage Pallets", "amount": "0.2"},
            {"group": "", "name": "Gauges", "amount": "0.5"},
            {"group": "", "name": "DM Water for Dycoat", "amount": "0.0"},
            {"group": "", "name": "Shift code punching Fixture", "amount": "0.7"},
            {"group": "", "name": "Welding Booth", "amount": "0.0"},
            {"group": "", "name": "Welding Fixture", "amount": "0.0"},
            {"group": "", "name": "Fan for Operators (Areas at Core, Decore, Casting, Fettling, HT (if any), Sh/blast (if any))", "amount": "0.1", "hl": True},
            {"group": "", "name": "Material handling (Crates+ Trolley)", "amount": ""},
            {"group": "", "name": "Material handling (Trolley - mould type)", "amount": "0.0"},
            {"group": "", "name": "Bend Removal Tool/ Fixture/ Gauge", "amount": ""},
            {"group": "", "name": "Profile Filter", "amount": "3.0"},
            {"group": "Common Facilities", "name": "Shot blasting Hanger", "amount": "0.5"},
            {"group": "", "name": "Stainless Steel shots for the volume", "amount": ""},
            {"group": "", "name": "HT Batch Code Punching Fixture", "amount": "1.0"},
            {"group": "", "name": "HT Basket cost", "amount": "1.5", "hl": True},
            {"group": "Die", "name": "Jet Cooling (Die Temp. Contr)", "amount": ""},
            {"group": "", "name": "Die service consumable", "amount": "0.0"},
        ],
        "operating_total": "21.0",
        "power": {
            "casting_cell": "219.0",
            "melting_furnace_capacity": "1000 T",
            "melting_furnace_power": "24.6",
            "heat_treatment": "Refer Note",
            "shot_blasting": "Refer Note",
            "discussed_with": "",
            "similar_part": "",
        },
        "testing_rows": [
            {"name": "Chemical Testing cost/ part", "value": "4.0"},
            {"name": "X Ray Testing cost / part", "value": ""},
            {"name": "Tensile Testing cost / part", "value": "5.8"},
            {"name": "Microstructure Testing cost / part", "value": "6.5"},
            {"name": "Hardness Testing cost / part", "value": "0.1"},
            {"name": "3D Inspection cost / part", "value": "0.8"},
            {"name": "Porosity Testing cost / part", "value": ""},
            {"name": "Others (if any)", "value": ""},
        ],
        "total_testing": "17.2",
        "assumptions": (
            "Assumptions/ Notes:  1) Refer additional sheet for remarks pertaining to casting. "
            "(2) The policy cost of die and handling NOT INCLUDED in the die cost. (3) Conversion "
            "rate considered as on estimation date for die cost/ machine cost/ accessories cost (if "
            "applicable)  (5) Melting furnace cost subject to change based on plant location. Confirm "
            "with Est. once finalised (6) Melting scrubber power rating NOT included in the above "
            "(7) Manpower mentioned above excluding melting, shot blasting & HT reqts (8) Cost of "
            "Stores & Tools, R&M expenses, Installation & Commissioning, Power cost are captured in "
            "pricing by Finance (9) Power details of Shot blasting & Heat treatment are not mentioned "
            "as it is considered in pricing based on shot rate and HT rate/ kg (10) The cost of Surface "
            "treatment (if any) to be obtained from Purchase only, NOT included in this estn"
        ),
        "prepared_by": "",
        "approved_by": "",
    }


def _machining() -> dict[str, Any]:
    return {
        "title": "RFQ Estimation for Machining",
        "form_ref": "",
        "casting_category": "Medium-Hor",
        "operations": [
            {"opn": "20", "desc": "TURNING CENTER- Diffuser  & Inlet M/cng (LT-20)", "cycle": "7.0", "mc_per_cell": "1", "mc_cost": "40,00,000", "cells": "1", "amount": "40,00,000"},
            {"opn": "30", "desc": "TURNING CENTER- Diffuser  & Inlet M/cng (LT-20)", "cycle": "5.9", "mc_per_cell": "1", "mc_cost": "40,00,000", "cells": "1", "amount": "40,00,000"},
            {"opn": "40", "desc": "TURNING CENTER- Outlet M/cng- SMALL, MEDIUM (LT-20)", "cycle": "5.0", "mc_per_cell": "1", "mc_cost": "40,00,000", "cells": "1", "amount": "40,00,000"},
            {"opn": "50", "desc": "VMC 450 & 5th AXIS  - WTH ROTARY TABLE, XYZ-600x450x500, TS-900 X 450", "cycle": "7.0", "mc_per_cell": "1", "mc_cost": "89,00,000", "cells": "1", "amount": "89,00,000"},
            {"opn": "60", "desc": "WASHING MACHINE", "cycle": "2.0", "mc_per_cell": "1", "mc_cost": "36,00,000", "cells": "1", "amount": "36,00,000"},
            {"opn": "70", "desc": "DRY CUM WET LEAK TEST", "cycle": "2.0", "mc_per_cell": "1", "mc_cost": "18,00,000", "cells": "1", "amount": "18,00,000"},
            {"opn": "80", "desc": "LASER MARKING WITH 2D SCANNER", "cycle": "2.0", "mc_per_cell": "1", "mc_cost": "24,00,000", "cells": "1", "amount": "24,00,000"},
            {"opn": "90", "desc": "FINAL INSPECTION AREA", "cycle": "2.0", "mc_per_cell": "1", "mc_cost": "2,00,000", "cells": "1", "amount": "2,00,000"},
            {"opn": "100", "desc": "ENDOSCOPE STATION", "cycle": "2.0", "mc_per_cell": "1", "mc_cost": "8,00,000", "cells": "1", "amount": "8,00,000"},
            {"opn": "110", "desc": "", "cycle": "", "mc_per_cell": "", "mc_cost": "", "cells": "0", "amount": "0"},
            {"opn": "#REF!", "desc": "", "cycle": "", "mc_per_cell": "", "mc_cost": "", "cells": "0", "amount": "0"},
            {"opn": "", "desc": "MATERIAL HANDLING IN MACHINE SHOP", "cycle": "", "mc_per_cell": "", "mc_cost": "", "cells": "", "amount": "0"},
        ],
        "cell_cycle_time": "7.00",
        "total_capital_expenditure": "2,97,00,000",
        # Operating cost — two columns of label/value pairs.
        "operating_left": [
            {"name": "Cost of Cutting tools", "value": "3,63,000"},
            {"name": "Cost of Tool Holders", "value": "22,00,000"},
            {"name": "Cost of Probing Unit (if any)", "value": "", "grey": True},
            {"name": "Cost of Fixtures", "value": "23,00,000"},
            {"name": "Cost of Gauges", "value": "6,80,000"},
            {"name": "Cost of Material Handling", "value": "3,00,000"},
            {"name": "", "value": ""},
            {"name": "Coolant oil cost", "value": "41,382"},
            {"name": "DM water cost for coolant, washing & Leak", "value": "21,780"},
            {"name": "Barcode label recurring cost", "value": ""},
            {"name": "Impregnation Basket cost", "value": "0"},
        ],
        "operating_total": "59,06,162",
        "operating_right": [
            {"name": "Cell Cycle Time (Min.)", "value": "7.00"},
            {"name": "Cell Capacity (Nos.)", "value": "43,682"},
            {"name": "Cell Utilisation", "value": "83%"},
            {"name": "No. of Cells", "value": "1"},
            {"name": "", "value": ""},
            {"name": "Power rating for cell (kw/hr)", "value": "115.0"},
            {"name": "Man Power / Shift / Cell", "value": "2"},
            {"name": "Floor area required / cell(Sq.M)", "value": "226.0"},
            {"name": "IMP Salvaging %", "value": "0%", "grey": True},
            {"name": "Setup changeover considered (Y/ N)", "value": "N"},
            {"name": "No of variants planned / cell", "value": "1"},
        ],
        "notes": (
            "1) Refer additional sheet for remarks pertaining to Machining (2) Estimated based on 3 "
            "shift basis only (3) Cost of Stores & Tools, R&M expenses, Installation & Commissioning, "
            "Power cost, load factor are captured in pricing by Finance (4) Details pertaining to "
            "Impregnation process (Cost, Man power, Power, Consumables like sealant etc) considered "
            "in pricing based on per kg cost. (5) The cost of Surface treatment (if any) to be obtained "
            "from Purchase only, NOT included in this estimation (6) Setup changeover time (if any) "
            "considered included in cycle time"
        ),
        "prepared_by": "",
        "approved_by": "",
    }


def _process_planning() -> dict[str, Any]:
    return {
        "title": "RFQ Process Planning Sheet",
        "date": "45695",
        "sequence": [
            {"machine": "MACHINE 1  : LATHE", "setup": "SETUP-1", "steps": ["Id forming profile forming"]},
            {"machine": "", "setup": "OUTLETTURNING", "steps": []},
            {"machine": "MACHINE 3  : LATHE", "setup": "", "steps": ["INLET OD FORMING"]},
            {"machine": "MACHINE 3  :  LATHE", "setup": "", "steps": ["OUTLET  OD FORMING"]},
            {"machine": "MACHINE 4  :  LATHE", "setup": "", "steps": [
                "Drilling Ø6.2 - 1 Nos",
                "Drilling Ø1.65 - 1 Nos",
                "Neme plate drilling",
                "profile form milling",
                "Slot milling",
            ]},
        ],
    }


def _assembly() -> dict[str, Any]:
    return {
        "title": "RFQ ESTIMATION FOR ASSEMBLY",
        "form_ref": "",
        "cycle_time": [
            {"name": "Cycle Time (min)", "assembly": "0.0", "afm": "0.0"},
            {"name": "Output Per Hour (Nos)", "assembly": "0", "afm": "0"},
            {"name": "Cell Capacity (Nos)", "assembly": "0", "afm": "0"},
            {"name": "Cell Utilisation", "assembly": "0%", "afm": "0.0%"},
            {"name": "No. of cells required", "assembly": "0", "afm": "0"},
        ],
        "before_afm_assembly": [
            {"name": "Assembly station / Fixture", "capex": "", "operating": ""},
            {"name": "Pokayoke system", "capex": "", "operating": ""},
            {"name": "Nut runner", "capex": "", "operating": ""},
            {"name": "Special Purpose Machine/ Fixture", "capex": "", "operating": ""},
            {"name": "Rivetting Machine / Fixture", "capex": "", "operating": ""},
            {"name": "Gauges", "capex": "", "operating": ""},
            {"name": "Other Accessories (if any)", "capex": "", "operating": ""},
        ],
        "total_assembly_investment": {"capex": "0.00", "operating": "0.00"},
        "total_assembly_investment_all": {"capex": "0.00", "operating": "0.00"},
        "assembly_params": [
            {"name": "Sealant consumption/ part (if any) (ml) loc tite 648", "value": "0.0"},
            {"name": "Power rating (Kw/hr)", "value": "0.0"},
            {"name": "Is it feasible to use M/cng operator for assembly (Yes / No)", "value": "NO"},
            {"name": "Manpower / shift/ cell", "value": "1.0"},
            {"name": "Floor space required for assembly station (Sq.m/ cell)", "value": "0.0"},
        ],
        "after_afm_involved": "0.0",
        "before_afm_machining": [
            {"name": "Vertical M/cng Center", "capex": "", "operating": "", "cycle": ""},
            {"name": "Turning Centers", "capex": "", "operating": "", "cycle": ""},
            {"name": "Special Purpose Machine", "capex": "", "operating": "", "cycle": ""},
            {"name": "Turning Centers", "capex": "", "operating": "", "cycle": ""},
            {"name": "Washing Machine", "capex": "", "operating": "", "cycle": ""},
            {"name": "Leak Testing Machine", "capex": "", "operating": "", "cycle": ""},
            {"name": "Deburring Unit / Air cleaning / Final Inspection", "capex": "", "operating": "", "cycle": ""},
            {"name": "Tool Holders cost", "capex": "", "operating": "", "cycle": ""},
            {"name": "Consumable tools cost", "capex": "", "operating": "", "cycle": ""},
            {"name": "Fixture Cost", "capex": "", "operating": "", "cycle": ""},
            {"name": "Gauge cost", "capex": "", "operating": "", "cycle": ""},
        ],
        "total_afm_investment": {"capex": "0", "operating": "0"},
        "total_afm_investment_all": {"capex": "0", "operating": "0"},
        "total_assy_investments": {"capex": "0", "operating": "0"},
        "afm_params": [
            {"name": "Power rating (Kw/hr)", "value": "-"},
            {"name": "Is it feasible to use M/cng cell operator for after assembly m/cng (Yes / No)", "value": "No"},
            {"name": "Manpower / shift/ cell", "value": "1.0"},
            {"name": "Floor space required for after assembly m/cng cell (Sq.m/ cell)", "value": "-"},
        ],
        "machined_part_rev": "",
        "casting_part_rev": "",
        "child_part_nos": "",
        "prepared_by": "",
        "approved_by": "",
    }


def _remarks() -> dict[str, Any]:
    return {
        "title": "RFQ REMARKS",
        "casting_remarks": [
            {"text": "Product design changes required.", "tone": "band"},
            {"text": "Casting weight given in the drawing, Machining weight extracted from 3d.", "tone": "plain"},
            {"text": "Average wall thcikness 5.0 mm.", "tone": "plain"},
            {"text": "Heat treament basket in -house 50 Nos", "tone": "plain"},
            {"text": (
                "As per the design input, we have determined that the AFM process is not required for "
                "this part. Instead, we will incorporate the following factors into our pricing:\n\n"
                "1. Special sand core cost : Rs. 110/kg\n"
                "2. New hydraulic core shooting process\n"
                "3. Dedicated trolloy for sand core movement.\n"
                "4. Special care and handling for core testing\n\n"
                "Please refer to the email below fro design reference."
            ), "tone": "highlight"},
        ],
        "machining_remarks": [
            {"text": "Leak testing pressure 2.4 bar @ 1.25 cc/min", "tone": "band"},
            {"text": "Required product design change in the machining feasibility  clamping and work support will be discussed during RTS.", "tone": "plain"},
            {"text": (
                "Estimation to be reviewed after RTS / DQR and Impact if any interms of cycle time or "
                "cost will be communicated accordingly with reference to engineering changes based on "
                "DFM / DFA agreed with customer."
            ), "tone": "warn"},
        ],
        "assembly_remarks": [],
    }


def _packing() -> dict[str, Any]:
    return {
        "title": "RFQ ESTIMATION FOR PACKING 334",
        "banner": "Expendable -  Packing Box qunaity working",
        "part_size": {"l": "242", "b": "211", "h": "134"},
        "packing_box_size": {"l": "1100", "b": "910", "h": "1000"},
        "allowances": {"l": "10", "b": "10", "h": "10"},
        "arrangements": [
            {"idx": "1", "l": "4.00", "b": "4.00", "h": "7.00", "components": "112"},
            {"idx": "2", "l": "5.00", "b": "6.00", "h": "4.00", "components": "120"},
            {"idx": "3", "l": "8.00", "b": "3.00", "h": "4.00", "components": "96"},
            {"idx": "4", "l": "4.00", "b": "6.00", "h": "4.00", "components": "96"},
            {"idx": "5", "l": "4.00", "b": "8.00", "h": "4.00", "components": "128"},
            {"idx": "6", "l": "7.00", "b": "3.00", "h": "5.00", "components": "105"},
        ],
        "per_box": "120",
        "notes": "Protection cap to be considered in pricing.",
    }


def default_context() -> dict[str, Any]:
    """Return a fresh, deep-copyable default context for the report."""
    return {
        "header": _header(),
        "casting": _casting(),
        "machining": _machining(),
        "process_planning": _process_planning(),
        "assembly": _assembly(),
        "remarks": _remarks(),
        "packing": _packing(),
    }


def deep_merge(base: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively merge ``overrides`` onto a deep copy of ``base``.

    Dicts merge key-by-key. Any non-dict value (including lists) replaces the
    base value wholesale — so a caller sending ``machining.operations`` supplies
    the entire operations list, not a per-row patch. ``None`` override values are
    ignored so partial payloads never blank out a reference default.
    """
    result = copy.deepcopy(base)
    if not overrides:
        return result
    for key, value in overrides.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
