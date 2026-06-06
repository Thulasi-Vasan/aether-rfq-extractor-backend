import re

def normalize(s: str) -> str:
    if not s: return ""
    return re.sub(r"[^a-zA-Z0-9]+", "", s).lower()

from typing import Any, Callable
import re

def _get_machine_val(r: Any, op_name: str, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    page = r.pages[0]
    items = getattr(page, "output_machine_details", [])
    for item in items:
        if isinstance(item, dict) and item.get("operation") == op_name:
            return item.get(key)
        elif hasattr(item, "operation") and getattr(item, "operation") == op_name:
            return getattr(item, key, None)
    return None

def _get_testing_val(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    testing = getattr(r.pages[0], "testing_cost_details", {})
    if isinstance(testing, dict):
        return testing.get(key)
    return getattr(testing, key, None)

def _get_power_val(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    power = getattr(r.pages[0], "power_rating_details", {})
    if isinstance(power, dict):
        return power.get(key)
    return getattr(power, key, None)

def _get_die_val(r: Any, index: int, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    die = getattr(r.pages[0], "die_details", {})
    items = die.get("capital_items", []) if isinstance(die, dict) else getattr(die, "capital_items", [])
    if items and len(items) > index:
        item = items[index]
        return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    return None

def _get_die_life(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    die = getattr(r.pages[0], "die_details", {})
    life = die.get("life", {}) if isinstance(die, dict) else getattr(die, "life", {})
    return life.get(key) if isinstance(life, dict) else getattr(life, key, None)


def _get_header_val(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    header = getattr(r.pages[0], "header", {})
    if isinstance(header, dict):
        return header.get(key)
    return getattr(header, key, None)

def _get_casting_val(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages:
        return None
    casting = getattr(r.pages[0], "casting_cell_details", {})
    if isinstance(casting, dict):
        return casting.get(key)
    return getattr(casting, key, None)

def _get_machining_header_val(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or len(r.pages) < 3:
        return None
    header = getattr(r.pages[2], "header", {})
    if isinstance(header, dict):
        return header.get(key)
    return getattr(header, key, None)

def _get_machining_cell_summary(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or len(r.pages) < 3:
        return None
    summary = getattr(r.pages[2], "cell_summary", {})
    if isinstance(summary, dict):
        return summary.get(key)
    return getattr(summary, key, None)

def _get_machining_resource(r: Any, key: str) -> Any:
    if not hasattr(r, "pages") or len(r.pages) < 3:
        return None
    res = getattr(r.pages[2], "resource_requirements", {})
    if isinstance(res, dict):
        return res.get(key)
    return getattr(res, key, None)

def _get_machining_op_val(r: Any, match_str: str, key: str) -> Any:
    if not hasattr(r, "pages") or len(r.pages) < 3: return None
    ops = getattr(r.pages[2], "machining_operations", [])
    if not isinstance(ops, list): return None
    for op in ops:
        desc = op.get("description", "") if isinstance(op, dict) else getattr(op, "description", "")
        if normalize(match_str) in normalize(desc) or normalize(desc) in normalize(match_str):
            return op.get(key) if isinstance(op, dict) else getattr(op, key, None)
    return None

def _get_machining_op_cost(r: Any, match_str: str, key: str) -> Any:
    if not hasattr(r, "pages") or len(r.pages) < 3: return None
    op_costs = getattr(r.pages[2], "operating_costs", [])
    if not isinstance(op_costs, list): return None
    for cat in op_costs:
        for item in (cat.get("items", []) if isinstance(cat, dict) else []):
            desc = item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
            if normalize(match_str) in normalize(desc) or normalize(desc) in normalize(match_str):
                return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    return None

def _get_assembly_val(r: Any, top_key: str, sub_key: str | None, key: str) -> Any:
    if not hasattr(r, "pages"): return None
    page = next((p for p in r.pages if getattr(p, "page_type", "") == "assembly_estimation"), None)
    if not page: return None
    top_obj = getattr(page, top_key, {}) if top_key else page
    if not isinstance(top_obj, dict): top_obj = getattr(top_obj, "__dict__", {})
    
    if sub_key:
        sub_obj = top_obj.get(sub_key, {})
        if not isinstance(sub_obj, dict): sub_obj = getattr(sub_obj, "__dict__", {})
        return sub_obj.get(key)
    return top_obj.get(key)

def _get_assembly_investment(r: Any, section_key: str, match_str: str, key: str) -> Any:
    if not hasattr(r, "pages"): return None
    page = next((p for p in r.pages if getattr(p, "page_type", "") == "assembly_estimation"), None)
    if not page: return None
    
    section = getattr(page, section_key, {})
    if not isinstance(section, dict): section = getattr(section, "__dict__", {})
    
    items = section.get("items", [])
    for item in items:
        desc = item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
        if normalize(match_str) in normalize(desc) or normalize(desc) in normalize(match_str):
            return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    return None

EXCEL_MAPPING: dict[str, Callable[[Any], Any]] = {
    # Header Details (GDC)
    "C2": lambda r: _get_header_val(r, "rfq_no"),
    "C4": lambda r: _get_header_val(r, "customer"),
    "G4": lambda r: _get_header_val(r, "annual_volume_nos"),
    "G5": lambda r: (_get_header_val(r, "annual_volume_nos") * 1.15) if isinstance(_get_header_val(r, "annual_volume_nos"), (int, float)) else None,
    "C5": lambda r: _get_header_val(r, "final_part_no"),
    "C6": lambda r: _get_header_val(r, "final_part_rev_no"),
    "C7": lambda r: _get_header_val(r, "description"),
    "C8": lambda r: _get_header_val(r, "alloy"),
    "G8": lambda r: _get_header_val(r, "machined_part_weight_kg"),
    "G9": lambda r: _get_header_val(r, "casting_weight_kg"),
    "G10": lambda r: _get_header_val(r, "lbh_mm").get("length") if isinstance(_get_header_val(r, "lbh_mm"), dict) else None,
    "G11": lambda r: _get_header_val(r, "lbh_mm").get("breadth") if isinstance(_get_header_val(r, "lbh_mm"), dict) else None,
    "G12": lambda r: _get_header_val(r, "lbh_mm").get("height") if isinstance(_get_header_val(r, "lbh_mm"), dict) else None,
    "C10": lambda r: "Domestic",
    "D10": lambda r: "CIF",

    # Packaging
    "AM10": lambda r: _get_header_val(r, "lbh_mm").get("length") if isinstance(_get_header_val(r, "lbh_mm"), dict) else None,
    "AM11": lambda r: _get_header_val(r, "lbh_mm").get("breadth") if isinstance(_get_header_val(r, "lbh_mm"), dict) else None,
    "AM12": lambda r: _get_header_val(r, "lbh_mm").get("height") if isinstance(_get_header_val(r, "lbh_mm"), dict) else None,

    # Header Details (Machining)
    "AC10": lambda r: _get_machining_header_val(r, "rfq_no"),
    "AC11": lambda r: _get_machining_header_val(r, "customer"),
    "AI11": lambda r: _get_machining_header_val(r, "annual_volume_nos"),
    "AC12": lambda r: _get_machining_header_val(r, "final_part_no"),
    "AI12": lambda r: _get_machining_header_val(r, "annual_volume_including_rejection_nos"),
    "AC13": lambda r: _get_machining_header_val(r, "final_part_rev_no"),
    "AI13": lambda r: _get_machining_header_val(r, "machined_part_weight_kg"),
    "AC14": lambda r: _get_machining_header_val(r, "description"),

    # Machining Summaries
    "AI42": lambda r: _get_machining_cell_summary(r, "cell_cycle_time_min"),
    "AI43": lambda r: _get_machining_cell_summary(r, "cell_capacity_nos"),
    "AI44": lambda r: _get_machining_cell_summary(r, "cell_utilisation_percent"),
    "AI45": lambda r: _get_machining_cell_summary(r, "no_of_cells"),
    "AI47": lambda r: _get_machining_resource(r, "power_rating_for_cell_kw_hr"),
    "AI48": lambda r: _get_machining_resource(r, "man_power_per_shift_per_cell"),
    "AI49": lambda r: _get_machining_resource(r, "floor_area_required_per_cell_sq_m"),

    # Output Machine details
    "L12": lambda r: _get_machine_val(r, "Sand core 1", "no_of_cavities_or_loading"),
    "M12": lambda r: _get_machine_val(r, "Sand core 1", "cycle_time_min"),
    "N12": lambda r: _get_machine_val(r, "Sand core 1", "output_per_hr"),

    "L13": lambda r: _get_machine_val(r, "Sand core 2", "no_of_cavities_or_loading"),
    "M13": lambda r: _get_machine_val(r, "Sand core 2", "cycle_time_min"),
    "N13": lambda r: _get_machine_val(r, "Sand core 2", "output_per_hr"),

    "L14": lambda r: _get_machine_val(r, "Sand core 3", "no_of_cavities_or_loading"),
    "M14": lambda r: _get_machine_val(r, "Sand core 3", "cycle_time_min"),
    "N14": lambda r: _get_machine_val(r, "Sand core 3", "output_per_hr"),

    "L15": lambda r: _get_machine_val(r, "Sand core 4", "no_of_cavities_or_loading"),
    "M15": lambda r: _get_machine_val(r, "Sand core 4", "cycle_time_min"),
    "N15": lambda r: _get_machine_val(r, "Sand core 4", "output_per_hr"),

    "L16": lambda r: _get_machine_val(r, "Decore", "no_of_cavities_or_loading"),
    "M16": lambda r: _get_machine_val(r, "Decore", "cycle_time_min"),
    "N16": lambda r: _get_machine_val(r, "Decore", "output_per_hr"),



    "L17": lambda r: _get_machine_val(r, "Casting", "no_of_cavities_or_loading"),
    "M17": lambda r: _get_machine_val(r, "Casting", "cycle_time_min"),
    "N17": lambda r: _get_machine_val(r, "Casting", "output_per_hr"),

    "L18": lambda r: _get_machine_val(r, "Cutting 1", "no_of_cavities_or_loading"),
    "M18": lambda r: _get_machine_val(r, "Cutting 1", "cycle_time_min"),
    "N18": lambda r: _get_machine_val(r, "Cutting 1", "output_per_hr"),

    "L19": lambda r: _get_machine_val(r, "Cutting 2", "no_of_cavities_or_loading"),
    "M19": lambda r: _get_machine_val(r, "Cutting 2", "cycle_time_min"),
    "N19": lambda r: _get_machine_val(r, "Cutting 2", "output_per_hr"),

    "L20": lambda r: _get_machine_val(r, "Linishing", "no_of_cavities_or_loading"),
    "M20": lambda r: _get_machine_val(r, "Linishing", "cycle_time_min"),
    "N20": lambda r: _get_machine_val(r, "Linishing", "output_per_hr"),

    "L21": lambda r: _get_machine_val(r, "Shot blasting", "no_of_cavities_or_loading"),
    "M21": lambda r: _get_machine_val(r, "Shot blasting", "cycle_time_min"),
    "N21": lambda r: _get_machine_val(r, "Shot blasting", "output_per_hr"),

    "S15": lambda r: _get_casting_val(r, "weight_of_sand_core_per_part_kg"),
    "S16": lambda r: _get_casting_val(r, "man_power_per_shift_per_cell"),
    "S17": lambda r: _get_casting_val(r, "floor_space_per_cell_sq_m"),
    "S19": lambda r: _get_casting_val(r, "shot_blasting_type"),
    "S21": lambda r: _get_casting_val(r, "surface_coating_involved"),

    # Testing costs
    "N59": lambda r: _get_testing_val(r, "chemical_testing_cost_per_part_rs"),
    "N60": lambda r: _get_testing_val(r, "x_ray_testing_cost_per_part_rs"),
    "N66": lambda r: _get_testing_val(r, "porosity_testing_cost_per_part_rs"),
    "N63": lambda r: _get_testing_val(r, "microstructure_testing_cost_per_part_rs"),
    "N64": lambda r: _get_testing_val(r, "hardness_testing_cost_per_part_rs"),
    "N62": lambda r: _get_testing_val(r, "tensile_testing_cost_per_part_rs"),
    "N65": lambda r: _get_testing_val(r, "inspection_3d_cost_per_part_rs"),
    "N68": lambda r: _get_testing_val(r, "others_cost_per_part_rs"),
    "N69": lambda r: _get_testing_val(r, "total_testing_cost_per_part_rs"),

    # Power costs
    "S62": lambda r: _get_power_val(r, "casting_cell_kw_hr"),
    "R64": lambda r: _get_power_val(r, "melting_furnace_capacity"),
    "S64": lambda r: _get_power_val(r, "melting_furnace_kw_hr"),
    "S65": lambda r: _get_power_val(r, "heat_treatment"),
    "S66": lambda r: _get_power_val(r, "shot_blasting"),

    # Die details
    "M55": lambda r: _get_die_val(r, 0, "no_of_dies"),
    "S55": lambda r: _get_die_val(r, 0, "amount_per_cell_rs_lac"),
    "N56": lambda r: _get_die_life(r, "die_life_shots"),
    "N57": lambda r: _get_die_life(r, "core_box_life_shots"),
    "AQ18": lambda r: r.pages[2].machining_operations[0].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 0 else None,
    "AS18": lambda r: r.pages[2].machining_operations[0].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 0 else None,
    "AT18": lambda r: r.pages[2].machining_operations[0].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 0 else None,
    "AQ19": lambda r: r.pages[2].machining_operations[1].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 1 else None,
    "AS19": lambda r: r.pages[2].machining_operations[1].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 1 else None,
    "AT19": lambda r: r.pages[2].machining_operations[1].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 1 else None,
    "AQ20": lambda r: r.pages[2].machining_operations[2].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 2 else None,
    "AS20": lambda r: r.pages[2].machining_operations[2].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 2 else None,
    "AT20": lambda r: r.pages[2].machining_operations[2].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 2 else None,
    "AQ21": lambda r: r.pages[2].machining_operations[3].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 3 else None,
    "AS21": lambda r: r.pages[2].machining_operations[3].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 3 else None,
    "AT21": lambda r: r.pages[2].machining_operations[3].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 3 else None,
    "AQ22": lambda r: r.pages[2].machining_operations[4].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 4 else None,
    "AS22": lambda r: r.pages[2].machining_operations[4].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 4 else None,
    "AT22": lambda r: r.pages[2].machining_operations[4].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 4 else None,
    "AQ23": lambda r: r.pages[2].machining_operations[5].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 5 else None,
    "AS23": lambda r: r.pages[2].machining_operations[5].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 5 else None,
    "AT23": lambda r: r.pages[2].machining_operations[5].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 5 else None,
    "AQ24": lambda r: r.pages[2].machining_operations[6].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 6 else None,
    "AS24": lambda r: r.pages[2].machining_operations[6].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 6 else None,
    "AT24": lambda r: r.pages[2].machining_operations[6].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 6 else None,
    "AQ25": lambda r: r.pages[2].machining_operations[7].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 7 else None,
    "AS25": lambda r: r.pages[2].machining_operations[7].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 7 else None,
    "AT25": lambda r: r.pages[2].machining_operations[7].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 7 else None,
    "AQ26": lambda r: r.pages[2].machining_operations[8].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 8 else None,
    "AS26": lambda r: r.pages[2].machining_operations[8].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 8 else None,
    "AT26": lambda r: r.pages[2].machining_operations[8].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 8 else None,
    "AQ27": lambda r: r.pages[2].machining_operations[9].get("description") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 9 else None,
    "AS27": lambda r: r.pages[2].machining_operations[9].get("cycle_time_min") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 9 else None,
    "AT27": lambda r: r.pages[2].machining_operations[9].get("machines_per_cell") if hasattr(r, "pages") and len(r.pages) >= 3 and hasattr(r.pages[2], "machining_operations") and isinstance(r.pages[2].machining_operations, list) and len(r.pages[2].machining_operations) > 9 else None,
    # Assembly Summaries (Cycle Time Details)
    "W10": lambda r: _get_assembly_val(r, "cycle_time_details", "assembly", "cycle_time_min"),
    "X10": lambda r: _get_assembly_val(r, "cycle_time_details", "after_assembly_machining", "cycle_time_min"),
    "W11": lambda r: _get_assembly_val(r, "cycle_time_details", "assembly", "output_per_hour_nos"),
    "X11": lambda r: _get_assembly_val(r, "cycle_time_details", "after_assembly_machining", "output_per_hour_nos"),
    "W12": lambda r: _get_assembly_val(r, "cycle_time_details", "assembly", "cell_capacity_nos"),
    "X12": lambda r: _get_assembly_val(r, "cycle_time_details", "after_assembly_machining", "cell_capacity_nos"),
    "W13": lambda r: _get_assembly_val(r, "cycle_time_details", "assembly", "cell_utilisation_percent"),
    "X13": lambda r: _get_assembly_val(r, "cycle_time_details", "after_assembly_machining", "cell_utilisation_percent"),
    "W14": lambda r: _get_assembly_val(r, "cycle_time_details", "assembly", "no_of_cells_required"),
    "X14": lambda r: _get_assembly_val(r, "cycle_time_details", "after_assembly_machining", "no_of_cells_required"),
    # Assembly Cost Details
    "W17": lambda r: _get_assembly_investment(r, "assembly_investments", "Assembly station", "capex_rs"),
    "X17": lambda r: _get_assembly_investment(r, "assembly_investments", "Assembly station", "operating_rs"),
    "W18": lambda r: _get_assembly_investment(r, "assembly_investments", "Pokayoke system", "capex_rs"),
    "X18": lambda r: _get_assembly_investment(r, "assembly_investments", "Pokayoke system", "operating_rs"),
    "W19": lambda r: _get_assembly_investment(r, "assembly_investments", "Special Purpose Machine", "capex_rs"),
    "X19": lambda r: _get_assembly_investment(r, "assembly_investments", "Special Purpose Machine", "operating_rs"),
    "W23": lambda r: _get_assembly_investment(r, "assembly_investments", "Gauges", "capex_rs"),
    "X23": lambda r: _get_assembly_investment(r, "assembly_investments", "Gauges", "operating_rs"),
    # Assembly Resource Requirements
    "W27": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "sealant_consumption_per_part_ml"),
    "X27": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "sealant_consumption_per_part_ml"),
    "W28": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "power_rating_kw_hr"),
    "X28": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "power_rating_kw_hr"),
    "W29": lambda r: "Y" if _get_assembly_val(r, "assembly_resource_requirements", None, "feasible_to_use_machining_operator_for_assembly") else "N",
    "X29": lambda r: "Y" if _get_assembly_val(r, "assembly_resource_requirements", None, "feasible_to_use_machining_operator_for_assembly") else "N",
    "W30": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "manpower_per_shift_per_cell"),
    "X30": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "manpower_per_shift_per_cell"),
    "W31": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "floor_space_required_sq_m_per_cell"),
    "X31": lambda r: _get_assembly_val(r, "assembly_resource_requirements", None, "floor_space_required_sq_m_per_cell"),
    "W33": lambda r: "Y" if _get_assembly_val(r, "after_assembly_machining", None, "involved") else "N",
    "X33": lambda r: "Y" if _get_assembly_val(r, "after_assembly_machining", None, "involved") else "N",
    # After Assembly Machining Cost details
    "W35": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Vertical M/cng Center", "capex_rs"),
    "X35": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Vertical M/cng Center", "operating_rs"),
    "Y35": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Vertical M/cng Center", "cycle_time_min"),
    "W38": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Turning Centers", "capex_rs"),
    "X38": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Turning Centers", "operating_rs"),
    "Y38": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Turning Centers", "cycle_time_min"),
    "W39": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Washing Machine", "capex_rs"),
    "X39": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Washing Machine", "operating_rs"),
    "Y39": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Washing Machine", "cycle_time_min"),
    "W40": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Leak Testing Machine", "capex_rs"),
    "X40": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Leak Testing Machine", "operating_rs"),
    "Y40": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Leak Testing Machine", "cycle_time_min"),
    "W41": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Deburring Unit", "capex_rs"),
    "X41": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Deburring Unit", "operating_rs"),
    "Y41": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Deburring Unit", "cycle_time_min"),
    "W43": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Consumable tools cost", "capex_rs"),
    "X43": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Consumable tools cost", "operating_rs"),
    "Y43": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Consumable tools cost", "cycle_time_min"),
    "W44": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Fixture Cost", "capex_rs"),
    "X44": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Fixture Cost", "operating_rs"),
    "Y44": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Fixture Cost", "cycle_time_min"),
    "W45": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Gauge cost", "capex_rs"),
    "X45": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Gauge cost", "operating_rs"),
    "Y45": lambda r: _get_assembly_investment(r, "after_assembly_machining", "Gauge cost", "cycle_time_min"),
    # After Assembly Resource Reqs
    "W51": lambda r: _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "power_rating_kw_hr"),
    "X51": lambda r: _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "power_rating_kw_hr"),
    "W52": lambda r: "Y" if _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "feasible_to_use_machining_cell_operator") else "N",
    "X52": lambda r: "Y" if _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "feasible_to_use_machining_cell_operator") else "N",
    "W53": lambda r: _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "manpower_per_shift_per_cell"),
    "X53": lambda r: _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "manpower_per_shift_per_cell"),
    "W54": lambda r: _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "floor_space_required_sq_m_per_cell"),
    "X54": lambda r: _get_assembly_val(r, "after_assembly_machining", "resource_requirements", "floor_space_required_sq_m_per_cell"),
    "AH36": lambda r: _get_machining_op_val(r, "MATERIAL HANDLING IN MACHINE SHOP", "amount_rs") or _get_machining_op_val(r, "MATERIAL HANDLING IN MACHINE SHOP", "machine_cost_rs"),
    "AE38": lambda r: _get_machining_cell_summary(r, "cell_cycle_time_min"),
    "AI38": lambda r: _get_machining_cell_summary(r, "total_capital_expenditure_rs"),
    # Machining Summaries in AI column
    "AI42": lambda r: _get_machining_cell_summary(r, "cell_cycle_time_min"),
    "AI43": lambda r: _get_machining_cell_summary(r, "cell_capacity_nos"),
    "AI44": lambda r: _get_machining_cell_summary(r, "cell_utilisation_percent"),
    "AI45": lambda r: _get_machining_cell_summary(r, "no_of_cells"),
    "AI47": lambda r: _get_machining_resource(r, "power_rating_for_cell_kw_hr"),
    "AI48": lambda r: _get_machining_resource(r, "man_power_per_shift_per_cell"),
    "AI49": lambda r: _get_machining_resource(r, "floor_area_required_per_cell_sq_m"),
    "AI50": lambda r: _get_machining_resource(r, "imp_salvaging_percent"),
    "AI51": lambda r: "Y" if _get_machining_resource(r, "setup_changeover_considered") else "N",
    "AI52": lambda r: _get_machining_resource(r, "no_of_variants_planned_per_cell"),
    # Machining Operating Costs in AD and AR columns
    "AD42": lambda r: _get_machining_op_cost(r, "Cost of Cutting tools", "amount_rs"),
    "AR42": lambda r: _get_machining_op_cost(r, "Cost of Cutting tools", "amount_rs"),
    "AD43": lambda r: _get_machining_op_cost(r, "Cost of Tool Holders", "amount_rs"),
    "AR43": lambda r: _get_machining_op_cost(r, "Cost of Tool Holders", "amount_rs"),
    "AD44": lambda r: _get_machining_op_cost(r, "Cap Die cost", "amount_rs"),
    "AR44": lambda r: _get_machining_op_cost(r, "Cost of Probing Unit", "amount_rs"),
    "AD45": lambda r: _get_machining_op_cost(r, "Cost of Fixtures", "amount_rs"),
    "AR45": lambda r: _get_machining_op_cost(r, "Cost of Fixtures", "amount_rs"),
    "AD46": lambda r: _get_machining_op_cost(r, "Cost of Gauges", "amount_rs"),
    "AR46": lambda r: _get_machining_op_cost(r, "Cost of Gauges", "amount_rs"),
    "AD47": lambda r: _get_machining_op_cost(r, "Cost of Material Handling", "amount_rs"),
    "AR47": lambda r: _get_machining_op_cost(r, "Cost of Material Handling", "amount_rs"),
    "AD48": lambda r: _get_machining_op_cost(r, "CMM fixture", "amount_rs"),
    "AD49": lambda r: _get_machining_op_cost(r, "Coolant oil cost", "amount_rs"),
    "AR49": lambda r: _get_machining_op_cost(r, "Coolant oil cost", "amount_rs"),
    "AD50": lambda r: _get_machining_op_cost(r, "DM water cost for coolant", "amount_rs"),
    "AR50": lambda r: _get_machining_op_cost(r, "DM water cost for coolant", "amount_rs"),
    "AD51": lambda r: _get_machining_op_cost(r, "Barcode label", "amount_rs"),
    "AR51": lambda r: _get_machining_op_cost(r, "Barcode label", "amount_rs"),
    "AD52": lambda r: _get_machining_op_cost(r, "Impregnation Basket cost", "amount_rs"),
    "AR52": lambda r: _get_machining_op_cost(r, "Impregnation Basket cost", "amount_rs"),

    # Operations cost ( GDC )
    "S23": lambda r: _get_op_val(r, "Dressing Station", "amount_rs_lac"),
    "S24": lambda r: _get_op_val(r, "Core Painting Station", "amount_rs_lac"),
    "S25": lambda r: _get_op_val(r, "Core Handling Stand", "amount_rs_lac"),
    "S26": lambda r: _get_op_val(r, "Core Cavity Handling Trolleys", "amount_rs_lac"),
    "S27": lambda r: _get_op_val(r, "Core visual inspection / Table / tools", "amount_rs_lac"),
    "S28": lambda r: _get_op_val(r, "Vibro Decoring Hammer", "amount_rs_lac"),
    "S29": lambda r: _get_op_val(r, "Vibro Decoring Fixture", "amount_rs_lac"),
    "S30": lambda r: _get_op_val(r, "Casting Table", "amount_rs_lac"),
    "S31": lambda r: _get_op_val(r, "Casting & Sand collection Trolley", "amount_rs_lac"),
    "S32": lambda r: _get_op_val(r, "Furnace Dross, Rejection trolley & Ladle set", "amount_rs_lac"),
    "S33": lambda r: _get_op_val(r, "Cutting Fixture (Circular/ Riser/ Band)", "amount_rs_lac"),
    "S34": lambda r: _get_op_val(r, "Riser Collection Trolley", "amount_rs_lac"),
    "S35": lambda r: _get_op_val(r, "Fettling table with Indexing Head", "amount_rs_lac"),
    "S36": lambda r: _get_op_val(r, "Indexing Fixture", "amount_rs_lac"),
    "S37": lambda r: _get_op_val(r, "Fettling Table", "amount_rs_lac"),
    "S38": lambda r: _get_op_val(r, "Fettling Booth", "amount_rs_lac"),
    "S39": lambda r: _get_op_val(r, "Cell Formation Cost", "amount_rs_lac"),
    "S40": lambda r: _get_op_val(r, "Filing & Grinding Tools", "amount_rs_lac"),
    "S41": lambda r: _get_op_val(r, "Final Inspection Table (Post cast+ HT)", "amount_rs_lac"),
    "S42": lambda r: _get_op_val(r, "Storage Pallets", "amount_rs_lac"),
    "S43": lambda r: _get_op_val(r, "Gauges", "amount_rs_lac"),
    "Q44": lambda r: _get_op_val(r, "DM Water for Dycoat", "description"),
    "S44": lambda r: _get_op_val(r, "DM Water for Dycoat", "amount_rs_lac"),
    "Q45": lambda r: _get_op_val(r, "Shift code punching Fixture", "description"),
    "S45": lambda r: _get_op_val(r, "Shift code punching Fixture", "amount_rs_lac"),
    "S46": lambda r: _get_op_val(r, "Welding Booth", "amount_rs_lac"),
    "S47": lambda r: _get_op_val(r, "Welding Fixture", "amount_rs_lac"),
    "S48": lambda r: _get_op_val(r, "Fan for Operators (Areas at Core, Decore, Casting, Fettling, HT (if any), Sh/blast (if any))", "amount_rs_lac"),
    "S49": lambda r: _get_op_val(r, "Material handling (Crates+ Trolley)", "amount_rs_lac"),
    "S50": lambda r: _get_op_val(r, "Material handling (Trolley - mould type)", "amount_rs_lac"),
    "S51": lambda r: _get_op_val(r, "PROFILE BURNER", "amount_rs_lac"),
    "S52": lambda r: _get_op_val(r, "Others (if any) Profile Filter", "amount_rs_lac"),
    "S53": lambda r: _get_op_val(r, "Shot blasting Hanger", "amount_rs_lac"),
    "S54": lambda r: _get_op_val(r, "Stainless Steel shots for the volume", "amount_rs_lac"),
    "S55": lambda r: _get_op_val(r, "HT Batch Code Punching Fixture", "amount_rs_lac"),
    "S56": lambda r: _get_op_val(r, "HT Basket cost", "amount_rs_lac"),
    "S57": lambda r: _get_op_val(r, "Jet Cooling cost (Die Temp. Contr)", "amount_rs_lac"),
    "S58": lambda r: _get_op_val(r, "Die service consumable", "amount_rs_lac"),
    "S59": lambda r: _get_op_val(r, "Total Investment", "amount_rs_lac"),


    #Capital Investment ( GDC )
    "K23": lambda r: _get_cap_val(r, "Core shooting M/c", "utilisation_percent"),
    "L23": lambda r: _get_cap_val(r, "Core shooting M/c", "units"),
    "M23": lambda r: _get_cap_val(r, "Core shooting M/c", "amount_per_cell_rs_lac"),
    "K25": lambda r: _get_cap_val(r, "Core Painting Oven (if any)", "utilisation_percent"),
    "L24": lambda r: _get_cap_val(r, "Core Painting Oven (if any)", "units"),
    "M24": lambda r: _get_cap_val(r, "Core Painting Oven (if any)", "amount_per_cell_rs_lac"),
    "K25": lambda r: _get_cap_val(r, "Thermal Decoring M/c", "utilisation_percent"),
    "L25": lambda r: _get_cap_val(r, "Thermal Decoring M/c", "units"),
    "M25": lambda r: _get_cap_val(r, "Thermal Decoring M/c", "amount_per_cell_rs_lac"),
    "K26": lambda r: _get_cap_val(r, "Crane to handle basket", "utilisation_percent"),
    "L26": lambda r: _get_cap_val(r, "Crane to handle basket", "units"),
    "M26": lambda r: _get_cap_val(r, "Crane to handle basket", "amount_per_cell_rs_lac"),
    "K27": lambda r: _get_cap_val(r, "Vibro Decoring Machine", "utilisation_percent"),
    "L27": lambda r: _get_cap_val(r, "Vibro Decoring Machine", "units"),
    "M27": lambda r: _get_cap_val(r, "Vibro Decoring Machine", "amount_per_cell_rs_lac"),
    "K28": lambda r: _get_cap_val(r, "Tilting Machine", "utilisation_percent"),
    "L28": lambda r: _get_cap_val(r, "Tilting Machine", "units"),
    "M28": lambda r: _get_cap_val(r, "Tilting Machine", "amount_per_cell_rs_lac"),
    "K29": lambda r: _get_cap_val(r, "Vertical Machine", "utilisation_percent"),
    "L29": lambda r: _get_cap_val(r, "Vertical Machine", "units"),
    "M29": lambda r: _get_cap_val(r, "Vertical Machine", "amount_per_cell_rs_lac"),
    "K30": lambda r: _get_cap_val(r, "Stand type Machine", "utilisation_percent"),
    "L30": lambda r: _get_cap_val(r, "Stand type Machine", "units"),
    "M30": lambda r: _get_cap_val(r, "Stand type Machine", "amount_per_cell_rs_lac"),
    "K31": lambda r: _get_cap_val(r, "Hydraulic Power Pack", "utilisation_percent"),
    "L31": lambda r: _get_cap_val(r, "Hydraulic Power Pack", "units"),
    "M31": lambda r: _get_cap_val(r, "Hydraulic Power Pack", "amount_per_cell_rs_lac"),
    "K32": lambda r: _get_cap_val(r, "Holding furnace", "utilisation_percent"),
    "L32": lambda r: _get_cap_val(r, "Holding furnace", "units"),
    "M32": lambda r: _get_cap_val(r, "Holding furnace", "amount_per_cell_rs_lac"),
    "K33": lambda r: _get_cap_val(r, "Band saw machine", "utilisation_percent"),
    "L33": lambda r: _get_cap_val(r, "Band saw machine", "units"),
    "M33": lambda r: _get_cap_val(r, "Band saw machine", "amount_per_cell_rs_lac"),
    "K34": lambda r: _get_cap_val(r, "Circular saw cutting machine", "utilisation_percent"),
    "L34": lambda r: _get_cap_val(r, "Circular saw cutting machine", "units"),
    "M34": lambda r: _get_cap_val(r, "Circular saw cutting machine", "amount_per_cell_rs_lac"),
    "K35": lambda r: _get_cap_val(r, "Knock out press", "utilisation_percent"),
    "L35": lambda r: _get_cap_val(r, "Knock out press", "units"),
    "M35": lambda r: _get_cap_val(r, "Knock out press", "amount_per_cell_rs_lac"),
    "K36": lambda r: _get_cap_val(r, "Linishing Machine with Dust Extractor", "utilisation_percent"),
    "L36": lambda r: _get_cap_val(r, "Linishing Machine with Dust Extractor", "units"),
    "M36": lambda r: _get_cap_val(r, "Linishing Machine with Dust Extractor", "amount_per_cell_rs_lac"),
    "K37": lambda r: _get_cap_val(r, "Shift code punching Machine", "utilisation_percent"),
    "L37": lambda r: _get_cap_val(r, "Shift code punching Machine", "units"),
    "M37": lambda r: _get_cap_val(r, "Shift code punching Machine", "amount_per_cell_rs_lac"),
    "K38": lambda r: _get_cap_val(r, "Welding Machine", "utilisation_percent"),
    "L38": lambda r: _get_cap_val(r, "Welding Machine", "units"),
    "M38": lambda r: _get_cap_val(r, "Welding Machine", "amount_per_cell_rs_lac"),
    "J39": lambda r: _get_cap_val(r, "Bend Removal Press", "description"),
    "K39": lambda r: _get_cap_val(r, "Bend Removal Press", "utilisation_percent"),
    "L39": lambda r: _get_cap_val(r, "Bend Removal Press", "units"),
    "M39": lambda r: _get_cap_val(r, "Bend Removal Press", "amount_per_cell_rs_lac"),
    "K40": lambda r: _get_cap_val(r, "Robot Pouring & Extraction", "utilisation_percent"),
    "L40": lambda r: _get_cap_val(r, "Robot Pouring & Extraction", "units"),
    "M40": lambda r: _get_cap_val(r, "Robot Pouring & Extraction", "amount_per_cell_rs_lac"),
    "K41": lambda r: _get_cap_val(r, "Endoscope machine", "utilisation_percent"),
    "L41": lambda r: _get_cap_val(r, "Endoscope machine", "units"),
    "M41": lambda r: _get_cap_val(r, "Endoscope machine", "amount_per_cell_rs_lac"),
    "K42": lambda r: _get_cap_val(r, "Special Core handling / Testing", "utilisation_percent"),
    "L42": lambda r: _get_cap_val(r, "Special Core handling / Testing", "units"),
    "M42": lambda r: _get_cap_val(r, "Special Core handling / Testing", "amount_per_cell_rs_lac"),
    "K43": lambda r: _get_cap_val(r, "Component Extractor or Catcher", "utilisation_percent"),
    "L43": lambda r: _get_cap_val(r, "Component Extractor or Catcher", "units"),
    "M43": lambda r: _get_cap_val(r, "Component Extractor or Catcher", "amount_per_cell_rs_lac"),
    "K44": lambda r: _get_cap_val(r, "Air Balancer", "utilisation_percent"),
    "L44": lambda r: _get_cap_val(r, "Air Balancer", "units"),
    "M44": lambda r: _get_cap_val(r, "Air Balancer", "amount_per_cell_rs_lac"),
    "K45": lambda r: _get_cap_val(r, "Core Painting Oven (if any)", "utilisation_percent"),
    "L45": lambda r: _get_cap_val(r, "Core Painting Oven (if any)", "units"),
    "M45": lambda r: _get_cap_val(r, "Core Painting Oven (if any)", "amount_per_cell_rs_lac"),
    "K46": lambda r: _get_cap_val(r, "Endoscope machine", "utilisation_percent"),
    "L46": lambda r: _get_cap_val(r, "Endoscope machine", "units"),
    "M46": lambda r: _get_cap_val(r, "Endoscope machine", "amount_per_cell_rs_lac"),
    "K47": lambda r: _get_cap_val(r, "Deflashing station", "utilisation_percent"),
    "L47": lambda r: _get_cap_val(r, "Deflashing station", "units"),
    "M47": lambda r: _get_cap_val(r, "Deflashing station", "amount_per_cell_rs_lac"),
    "K48": lambda r: _get_cap_val(r, "Shot blasting M/c", "utilisation_percent"),
    "L48": lambda r: _get_cap_val(r, "Shot blasting M/c", "units"),
    "M48": lambda r: _get_cap_val(r, "Shot blasting M/c", "amount_per_cell_rs_lac"),
    "K49": lambda r: _get_cap_val(r, "Melting furnace", "utilisation_percent"),
    "L49": lambda r: _get_cap_val(r, "Melting furnace", "units"),
    "M49": lambda r: _get_cap_val(r, "Melting furnace", "amount_per_cell_rs_lac"),
    "K50": lambda r: _get_cap_val(r, "Melting furnace accessories (Fork lift, ATL, Degassing unit, Dross trolley, scrubber unit)", "utilisation_percent"),
    "L50": lambda r: _get_cap_val(r, "Melting furnace accessories (Fork lift, ATL, Degassing unit, Dross trolley, scrubber unit)", "units"),
    "M50": lambda r: _get_cap_val(r, "Melting furnace accessories (Fork lift, ATL, Degassing unit, Dross trolley, scrubber unit)", "amount_per_cell_rs_lac"),
    "K51": lambda r: _get_cap_val(r, "Heat Treatment Furnace (incl crane)", "utilisation_percent"),
    "L51": lambda r: _get_cap_val(r, "Heat Treatment Furnace (incl crane)", "units"),
    "M51": lambda r: _get_cap_val(r, "Heat Treatment Furnace (incl crane)", "amount_per_cell_rs_lac"),
    "K52": lambda r: _get_cap_val(r, "Heat Treatment BatchCode Punching M/c", "utilisation_percent"),
    "L52": lambda r: _get_cap_val(r, "Heat Treatment BatchCode Punching M/c", "units"),
    "M52": lambda r: _get_cap_val(r, "Heat Treatment BatchCode Punching M/c", "amount_per_cell_rs_lac"),
    "K53": lambda r: _get_cap_val(r, "Core placement fixture", "utilisation_percent"),
    "L53": lambda r: _get_cap_val(r, "Core placement fixture", "units"),
    "M53": lambda r: _get_cap_val(r, "Core placement fixture", "amount_per_cell_rs_lac"),
}

def set_cell_value(sheet, coord: str, value: Any):
    cell = sheet[coord]
    if type(cell).__name__ == "MergedCell":
        for merged_range in sheet.merged_cells.ranges:
            if coord in merged_range:
                top_left = merged_range.start_cell
                sheet.cell(row=top_left.row, column=top_left.column).value = value
                return
    else:
        cell.value = value

def _get_cap_val(r: Any, match_str: str, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages: return None
    normalized_match = normalize(match_str)
    candidates = []
    for cat in getattr(r.pages[0], "capital_investments", []):
        for item in (cat.get("items", []) if isinstance(cat, dict) else []):
            desc = item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
            normalized_desc = normalize(desc)
            if normalized_desc == normalized_match:
                return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            if normalized_match in normalized_desc or normalized_desc in normalized_match:
                candidates.append(item)
    if candidates:
        item = candidates[0]
        return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    return None

def _get_op_val(r: Any, match_str: str, key: str) -> Any:
    if not hasattr(r, "pages") or not r.pages: return None
    for cat in getattr(r.pages[0], "operating_costs", []):
        for item in (cat.get("items", []) if isinstance(cat, dict) else []):
            desc = item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
            if normalize(match_str) in normalize(desc) or normalize(desc) in normalize(match_str):
                return item.get(key) if isinstance(item, dict) else getattr(item, key, None)

    die = getattr(r.pages[0], "die_details", {})
    die_ops = die.get("operating_items", []) if isinstance(die, dict) else getattr(die, "operating_items", [])
    for item in die_ops:
        desc = item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
        if normalize(match_str) in normalize(desc) or normalize(desc) in normalize(match_str):
            return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    return None


# Maps each Excel cell to a machine-readable field key.
CELL_FIELD_KEYS: dict[str, str] = {
    "C2": "rfq_no", "C4": "customer", "G4": "annual_volume_nos",
    "G5": "annual_volume_with_rejection", "C5": "final_part_no",
    "C6": "final_part_rev_no", "C7": "description", "C8": "alloy",
    "G8": "machined_part_weight_kg", "G9": "casting_weight_kg",
    "G10": "lbh_length_mm", "G11": "lbh_breadth_mm", "G12": "lbh_height_mm",
    "C10": "geographical_segment", "D10": "pricing_basis",
    "AM10": "pkg_lbh_length_mm", "AM11": "pkg_lbh_breadth_mm", "AM12": "pkg_lbh_height_mm",
    "AC10": "machining_rfq_no", "AC11": "machining_customer",
    "AI11": "machining_annual_volume_nos", "AC12": "machining_final_part_no",
    "AI12": "machining_annual_volume_with_rejection", "AC13": "machining_final_part_rev_no",
    "AI13": "machining_part_weight_kg", "AC14": "machining_description",
    "AI42": "cell_cycle_time_min", "AI43": "cell_capacity_nos",
    "AI44": "cell_utilisation_percent", "AI45": "no_of_cells",
    "AI47": "power_rating_kw_hr", "AI48": "man_power_per_shift",
    "AI49": "floor_area_sq_m", "AI50": "imp_salvaging_percent",
    "AI51": "setup_changeover_considered", "AI52": "no_of_variants_per_cell",
    "L12": "sand_core_1_cavities", "M12": "sand_core_1_cycle_time", "N12": "sand_core_1_output_hr",
    "L13": "sand_core_2_cavities", "M13": "sand_core_2_cycle_time", "N13": "sand_core_2_output_hr",
    "L14": "sand_core_3_cavities", "M14": "sand_core_3_cycle_time", "N14": "sand_core_3_output_hr",
    "L15": "sand_core_4_cavities", "M15": "sand_core_4_cycle_time", "N15": "sand_core_4_output_hr",
    "L16": "decore_cavities", "M16": "decore_cycle_time", "N16": "decore_output_hr",
    "L17": "casting_cavities", "M17": "casting_cycle_time", "N17": "casting_output_hr",
    "L18": "cutting_1_cavities", "M18": "cutting_1_cycle_time", "N18": "cutting_1_output_hr",
    "L19": "cutting_2_cavities", "M19": "cutting_2_cycle_time", "N19": "cutting_2_output_hr",
    "L20": "linishing_cavities", "M20": "linishing_cycle_time", "N20": "linishing_output_hr",
    "L21": "shot_blasting_cavities", "M21": "shot_blasting_cycle_time", "N21": "shot_blasting_output_hr",
    "S15": "sand_core_weight_kg", "S16": "casting_man_power",
    "S17": "casting_floor_space_sq_m", "S19": "shot_blasting_type", "S21": "surface_coating_involved",
    "N59": "chemical_testing_cost_rs", "N60": "x_ray_testing_cost_rs",
    "N66": "porosity_testing_cost_rs", "N63": "microstructure_testing_cost_rs",
    "N64": "hardness_testing_cost_rs", "N62": "tensile_testing_cost_rs",
    "N65": "inspection_3d_cost_rs", "N68": "others_testing_cost_rs",
    "N69": "total_testing_cost_rs",
    "S62": "casting_cell_power_kw_hr", "R64": "melting_furnace_capacity",
    "S64": "melting_furnace_power_kw_hr", "S65": "heat_treatment_power", "S66": "shot_blasting_power",
    "M55": "no_of_dies", "S55": "die_amount_per_cell_rs_lac",
    "N56": "die_life_shots", "N57": "core_box_life_shots",
    "AQ18": "machining_op_1_description", "AS18": "machining_op_1_cycle_time", "AT18": "machining_op_1_machines",
    "AQ19": "machining_op_2_description", "AS19": "machining_op_2_cycle_time", "AT19": "machining_op_2_machines",
    "AQ20": "machining_op_3_description", "AS20": "machining_op_3_cycle_time", "AT20": "machining_op_3_machines",
    "AQ21": "machining_op_4_description", "AS21": "machining_op_4_cycle_time", "AT21": "machining_op_4_machines",
    "AQ22": "machining_op_5_description", "AS22": "machining_op_5_cycle_time", "AT22": "machining_op_5_machines",
    "AQ23": "machining_op_6_description", "AS23": "machining_op_6_cycle_time", "AT23": "machining_op_6_machines",
    "AQ24": "machining_op_7_description", "AS24": "machining_op_7_cycle_time", "AT24": "machining_op_7_machines",
    "AQ25": "machining_op_8_description", "AS25": "machining_op_8_cycle_time", "AT25": "machining_op_8_machines",
    "AQ26": "machining_op_9_description", "AS26": "machining_op_9_cycle_time", "AT26": "machining_op_9_machines",
    "AQ27": "machining_op_10_description", "AS27": "machining_op_10_cycle_time", "AT27": "machining_op_10_machines",
    "W10": "assembly_cycle_time_min", "X10": "aam_cycle_time_min",
    "W11": "assembly_output_per_hr", "X11": "aam_output_per_hr",
    "W12": "assembly_cell_capacity", "X12": "aam_cell_capacity",
    "W13": "assembly_cell_utilisation", "X13": "aam_cell_utilisation",
    "W14": "assembly_no_of_cells", "X14": "aam_no_of_cells",
    "W17": "assembly_station_capex", "X17": "assembly_station_operating",
    "W18": "pokayoke_system_capex", "X18": "pokayoke_system_operating",
    "W19": "spm_capex", "X19": "spm_operating",
    "W23": "gauges_capex", "X23": "gauges_operating",
    "W27": "sealant_consumption_ml", "X27": "aam_sealant_consumption_ml",
    "W28": "assembly_power_kw_hr", "X28": "aam_power_kw_hr",
    "W29": "use_machining_operator_assembly", "X29": "aam_use_machining_operator",
    "W30": "assembly_manpower", "X30": "aam_manpower",
    "W31": "assembly_floor_space_sq_m", "X31": "aam_floor_space_sq_m",
    "W33": "after_assembly_machining_involved", "X33": "aam_involved",
    "W35": "vmc_capex", "X35": "vmc_operating", "Y35": "vmc_cycle_time",
    "W38": "turning_center_capex", "X38": "turning_center_operating", "Y38": "turning_center_cycle_time",
    "W39": "washing_machine_capex", "X39": "washing_machine_operating", "Y39": "washing_machine_cycle_time",
    "W40": "leak_testing_capex", "X40": "leak_testing_operating", "Y40": "leak_testing_cycle_time",
    "W41": "deburring_unit_capex", "X41": "deburring_unit_operating", "Y41": "deburring_unit_cycle_time",
    "W43": "consumable_tools_capex", "X43": "consumable_tools_operating", "Y43": "consumable_tools_cycle_time",
    "W44": "fixture_cost_capex", "X44": "fixture_cost_operating", "Y44": "fixture_cost_cycle_time",
    "W45": "gauge_cost_capex", "X45": "gauge_cost_operating", "Y45": "gauge_cost_cycle_time",
    "W51": "aam_resource_power_kw_hr", "X51": "aam_resource_power_kw_hr_2",
    "W52": "aam_use_machining_cell_operator", "X52": "aam_use_machining_cell_operator_2",
    "W53": "aam_resource_manpower", "X53": "aam_resource_manpower_2",
    "W54": "aam_resource_floor_space", "X54": "aam_resource_floor_space_2",
    "AH36": "material_handling_machine_shop", "AE38": "machining_cell_cycle_time",
    "AI38": "total_capital_expenditure",
    "AD42": "cutting_tools_cost", "AR42": "cutting_tools_cost_2",
    "AD43": "tool_holders_cost", "AR43": "tool_holders_cost_2",
    "AD44": "cap_die_cost", "AR44": "probing_unit_cost",
    "AD45": "fixtures_cost", "AR45": "fixtures_cost_2",
    "AD46": "gauges_machining_cost", "AR46": "gauges_machining_cost_2",
    "AD47": "material_handling_cost", "AR47": "material_handling_cost_2",
    "AD48": "cmm_fixture_cost", "AD49": "coolant_oil_cost", "AR49": "coolant_oil_cost_2",
    "AD50": "dm_water_coolant_cost", "AR50": "dm_water_coolant_cost_2",
    "AD51": "barcode_label_cost", "AR51": "barcode_label_cost_2",
    "AD52": "impregnation_basket_cost", "AR52": "impregnation_basket_cost_2",
    "S23": "dressing_station_amount", "S24": "core_painting_station_amount",
    "S25": "core_handling_stand_amount", "S26": "core_cavity_trolleys_amount",
    "S27": "core_inspection_tools_amount", "S28": "vibro_decoring_hammer_amount",
    "S29": "vibro_decoring_fixture_amount", "S30": "casting_table_amount",
    "S31": "casting_sand_trolley_amount", "S32": "furnace_dross_trolley_amount",
    "S33": "cutting_fixture_amount", "S34": "riser_collection_trolley_amount",
    "S35": "fettling_table_indexing_amount", "S36": "indexing_fixture_amount",
    "S37": "fettling_table_amount", "S38": "fettling_booth_amount",
    "S39": "cell_formation_cost_amount", "S40": "filing_grinding_tools_amount",
    "S41": "final_inspection_table_amount", "S42": "storage_pallets_amount",
    "S43": "gauges_gdc_amount", "Q44": "dm_water_dycoat_description",
    "S44": "dm_water_dycoat_amount", "Q45": "shift_code_fixture_description",
    "S45": "shift_code_fixture_amount", "S46": "welding_booth_amount",
    "S47": "welding_fixture_amount", "S48": "fan_operators_amount",
    "S49": "material_handling_crates_amount", "S50": "material_handling_trolley_amount",
    "S51": "profile_burner_amount", "S52": "others_profile_filter_amount",
    "S53": "shot_blasting_hanger_amount", "S54": "ss_shots_amount",
    "S55": "ht_batch_code_fixture_amount", "S56": "ht_basket_cost_amount",
    "S57": "jet_cooling_amount", "S58": "die_service_consumable_amount",
    "S59": "total_operating_investment_amount",
    "K23": "core_shooting_utilisation", "L23": "core_shooting_units", "M23": "core_shooting_amount",
    "L24": "core_painting_oven_units", "M24": "core_painting_oven_amount",
    "K25": "thermal_decoring_utilisation", "L25": "thermal_decoring_units", "M25": "thermal_decoring_amount",
    "K26": "crane_basket_utilisation", "L26": "crane_basket_units", "M26": "crane_basket_amount",
    "K27": "vibro_decoring_machine_utilisation", "L27": "vibro_decoring_machine_units", "M27": "vibro_decoring_machine_amount",
    "K28": "tilting_machine_utilisation", "L28": "tilting_machine_units", "M28": "tilting_machine_amount",
    "K29": "vertical_machine_utilisation", "L29": "vertical_machine_units", "M29": "vertical_machine_amount",
    "K30": "stand_type_machine_utilisation", "L30": "stand_type_machine_units", "M30": "stand_type_machine_amount",
    "K31": "hydraulic_power_pack_utilisation", "L31": "hydraulic_power_pack_units", "M31": "hydraulic_power_pack_amount",
    "K32": "holding_furnace_utilisation", "L32": "holding_furnace_units", "M32": "holding_furnace_amount",
    "K33": "band_saw_utilisation", "L33": "band_saw_units", "M33": "band_saw_amount",
    "K34": "circular_saw_utilisation", "L34": "circular_saw_units", "M34": "circular_saw_amount",
    "K35": "knock_out_press_utilisation", "L35": "knock_out_press_units", "M35": "knock_out_press_amount",
    "K36": "linishing_machine_utilisation", "L36": "linishing_machine_units", "M36": "linishing_machine_amount",
    "K37": "shift_code_punching_utilisation", "L37": "shift_code_punching_units", "M37": "shift_code_punching_amount",
    "K38": "welding_machine_utilisation", "L38": "welding_machine_units", "M38": "welding_machine_amount",
    "J39": "bend_removal_press_description", "K39": "bend_removal_press_utilisation",
    "L39": "bend_removal_press_units", "M39": "bend_removal_press_amount",
    "K40": "robot_pouring_utilisation", "L40": "robot_pouring_units", "M40": "robot_pouring_amount",
    "K41": "endoscope_machine_utilisation", "L41": "endoscope_machine_units", "M41": "endoscope_machine_amount",
    "K42": "special_core_handling_utilisation", "L42": "special_core_handling_units", "M42": "special_core_handling_amount",
    "K43": "component_extractor_utilisation", "L43": "component_extractor_units", "M43": "component_extractor_amount",
    "K44": "air_balancer_utilisation", "L44": "air_balancer_units", "M44": "air_balancer_amount",
    "K45": "core_painting_oven_2_utilisation", "L45": "core_painting_oven_2_units", "M45": "core_painting_oven_2_amount",
    "K46": "endoscope_machine_2_utilisation", "L46": "endoscope_machine_2_units", "M46": "endoscope_machine_2_amount",
    "K47": "deflashing_station_utilisation", "L47": "deflashing_station_units", "M47": "deflashing_station_amount",
    "K48": "shot_blasting_mc_utilisation", "L48": "shot_blasting_mc_units", "M48": "shot_blasting_mc_amount",
    "K49": "melting_furnace_utilisation", "L49": "melting_furnace_units", "M49": "melting_furnace_amount",
    "K50": "melting_furnace_accessories_utilisation", "L50": "melting_furnace_accessories_units",
    "M50": "melting_furnace_accessories_amount",
    "K51": "ht_furnace_utilisation", "L51": "ht_furnace_units", "M51": "ht_furnace_amount",
    "K52": "ht_batch_code_mc_utilisation", "L52": "ht_batch_code_mc_units", "M52": "ht_batch_code_mc_amount",
    "K53": "core_placement_fixture_utilisation", "L53": "core_placement_fixture_units", "M53": "core_placement_fixture_amount",
}

# Human-readable labels for the provenance panel UI.
CELL_FIELD_LABELS: dict[str, str] = {
    "C2": "RFQ No.", "C4": "Customer", "G4": "Annual Volume (Nos)",
    "G5": "Annual Volume incl. Rejection (Nos)", "C5": "Final Part No.",
    "C6": "Final Part Rev. No.", "C7": "Part Description", "C8": "Alloy",
    "G8": "Machined Part Weight (kg)", "G9": "Casting Weight (kg)",
    "G10": "LBH Length (mm)", "G11": "LBH Breadth (mm)", "G12": "LBH Height (mm)",
    "C10": "Geographical Segment", "D10": "Pricing Basis",
    "AM10": "Pkg LBH Length (mm)", "AM11": "Pkg LBH Breadth (mm)", "AM12": "Pkg LBH Height (mm)",
    "AC10": "Machining RFQ No.", "AC11": "Machining Customer",
    "AI11": "Machining Annual Volume (Nos)", "AC12": "Machining Final Part No.",
    "AI12": "Machining Annual Volume incl. Rejection", "AC13": "Machining Part Rev. No.",
    "AI13": "Machining Part Weight (kg)", "AC14": "Machining Description",
    "AI42": "Cell Cycle Time (min)", "AI43": "Cell Capacity (Nos)",
    "AI44": "Cell Utilisation (%)", "AI45": "No. of Cells",
    "AI47": "Power Rating (kW/hr)", "AI48": "Manpower per Shift",
    "AI49": "Floor Area (sq.m)", "AI50": "Imp. Salvaging (%)",
    "AI51": "Setup/Changeover Considered", "AI52": "No. of Variants per Cell",
    "L12": "Sand Core 1 — Cavities", "M12": "Sand Core 1 — Cycle Time (min)", "N12": "Sand Core 1 — Output/hr",
    "L13": "Sand Core 2 — Cavities", "M13": "Sand Core 2 — Cycle Time (min)", "N13": "Sand Core 2 — Output/hr",
    "L14": "Sand Core 3 — Cavities", "M14": "Sand Core 3 — Cycle Time (min)", "N14": "Sand Core 3 — Output/hr",
    "L15": "Sand Core 4 — Cavities", "M15": "Sand Core 4 — Cycle Time (min)", "N15": "Sand Core 4 — Output/hr",
    "L16": "Decore — Cavities", "M16": "Decore — Cycle Time (min)", "N16": "Decore — Output/hr",
    "L17": "Casting — Cavities", "M17": "Casting — Cycle Time (min)", "N17": "Casting — Output/hr",
    "L18": "Cutting 1 — Cavities", "M18": "Cutting 1 — Cycle Time (min)", "N18": "Cutting 1 — Output/hr",
    "L19": "Cutting 2 — Cavities", "M19": "Cutting 2 — Cycle Time (min)", "N19": "Cutting 2 — Output/hr",
    "L20": "Linishing — Cavities", "M20": "Linishing — Cycle Time (min)", "N20": "Linishing — Output/hr",
    "L21": "Shot Blasting — Cavities", "M21": "Shot Blasting — Cycle Time (min)", "N21": "Shot Blasting — Output/hr",
    "S15": "Sand Core Weight per Part (kg)", "S16": "Manpower per Shift per Cell",
    "S17": "Floor Space per Cell (sq.m)", "S19": "Shot Blasting Type", "S21": "Surface Coating Involved",
    "N59": "Chemical Testing Cost/Part (₹)", "N60": "X-Ray Testing Cost/Part (₹)",
    "N66": "Porosity Testing Cost/Part (₹)", "N63": "Microstructure Testing Cost/Part (₹)",
    "N64": "Hardness Testing Cost/Part (₹)", "N62": "Tensile Testing Cost/Part (₹)",
    "N65": "3D Inspection Cost/Part (₹)", "N68": "Others Testing Cost/Part (₹)",
    "N69": "Total Testing Cost/Part (₹)",
    "S62": "Casting Cell Power (kW/hr)", "R64": "Melting Furnace Capacity",
    "S64": "Melting Furnace Power (kW/hr)", "S65": "Heat Treatment Power", "S66": "Shot Blasting Power",
    "M55": "No. of Dies", "S55": "Die Amount per Cell (₹ Lac)",
    "N56": "Die Life (shots)", "N57": "Core Box Life (shots)",
    "AQ18": "Machining Op 1 — Description", "AS18": "Machining Op 1 — Cycle Time", "AT18": "Machining Op 1 — Machines/Cell",
    "AQ19": "Machining Op 2 — Description", "AS19": "Machining Op 2 — Cycle Time", "AT19": "Machining Op 2 — Machines/Cell",
    "AQ20": "Machining Op 3 — Description", "AS20": "Machining Op 3 — Cycle Time", "AT20": "Machining Op 3 — Machines/Cell",
    "AQ21": "Machining Op 4 — Description", "AS21": "Machining Op 4 — Cycle Time", "AT21": "Machining Op 4 — Machines/Cell",
    "AQ22": "Machining Op 5 — Description", "AS22": "Machining Op 5 — Cycle Time", "AT22": "Machining Op 5 — Machines/Cell",
    "AQ23": "Machining Op 6 — Description", "AS23": "Machining Op 6 — Cycle Time", "AT23": "Machining Op 6 — Machines/Cell",
    "AQ24": "Machining Op 7 — Description", "AS24": "Machining Op 7 — Cycle Time", "AT24": "Machining Op 7 — Machines/Cell",
    "AQ25": "Machining Op 8 — Description", "AS25": "Machining Op 8 — Cycle Time", "AT25": "Machining Op 8 — Machines/Cell",
    "AQ26": "Machining Op 9 — Description", "AS26": "Machining Op 9 — Cycle Time", "AT26": "Machining Op 9 — Machines/Cell",
    "AQ27": "Machining Op 10 — Description", "AS27": "Machining Op 10 — Cycle Time", "AT27": "Machining Op 10 — Machines/Cell",
    "W10": "Assembly Cycle Time (min)", "X10": "After-Assembly Machining Cycle Time (min)",
    "W11": "Assembly Output/hr", "X11": "AAM Output/hr",
    "W12": "Assembly Cell Capacity", "X12": "AAM Cell Capacity",
    "W13": "Assembly Cell Utilisation (%)", "X13": "AAM Cell Utilisation (%)",
    "W14": "Assembly No. of Cells", "X14": "AAM No. of Cells",
    "W17": "Assembly Station — Capex (₹)", "X17": "Assembly Station — Operating (₹)",
    "W18": "Pokayoke System — Capex (₹)", "X18": "Pokayoke System — Operating (₹)",
    "W19": "Special Purpose Machine — Capex (₹)", "X19": "Special Purpose Machine — Operating (₹)",
    "W23": "Gauges — Capex (₹)", "X23": "Gauges — Operating (₹)",
    "W27": "Sealant Consumption/Part (ml)", "X27": "AAM Sealant Consumption/Part (ml)",
    "W28": "Assembly Power Rating (kW/hr)", "X28": "AAM Power Rating (kW/hr)",
    "W29": "Use Machining Operator for Assembly (Y/N)", "X29": "AAM Use Machining Operator (Y/N)",
    "W30": "Assembly Manpower/Shift/Cell", "X30": "AAM Manpower/Shift/Cell",
    "W31": "Assembly Floor Space (sq.m/Cell)", "X31": "AAM Floor Space (sq.m/Cell)",
    "W33": "After-Assembly Machining Involved (Y/N)", "X33": "AAM Involved (Y/N)",
    "W35": "VMC — Capex (₹)", "X35": "VMC — Operating (₹)", "Y35": "VMC — Cycle Time (min)",
    "W38": "Turning Centre — Capex (₹)", "X38": "Turning Centre — Operating (₹)", "Y38": "Turning Centre — Cycle Time",
    "W39": "Washing Machine — Capex (₹)", "X39": "Washing Machine — Operating (₹)", "Y39": "Washing Machine — Cycle Time",
    "W40": "Leak Testing Machine — Capex (₹)", "X40": "Leak Testing Machine — Operating (₹)", "Y40": "Leak Testing Machine — Cycle Time",
    "W41": "Deburring Unit — Capex (₹)", "X41": "Deburring Unit — Operating (₹)", "Y41": "Deburring Unit — Cycle Time",
    "W43": "Consumable Tools — Capex (₹)", "X43": "Consumable Tools — Operating (₹)", "Y43": "Consumable Tools — Cycle Time",
    "W44": "Fixture Cost — Capex (₹)", "X44": "Fixture Cost — Operating (₹)", "Y44": "Fixture Cost — Cycle Time",
    "W45": "Gauge Cost — Capex (₹)", "X45": "Gauge Cost — Operating (₹)", "Y45": "Gauge Cost — Cycle Time",
    "W51": "AAM Resource Power (kW/hr)", "X51": "AAM Resource Power (kW/hr) [2]",
    "W52": "AAM Use Machining Cell Operator (Y/N)", "X52": "AAM Use Machining Cell Operator (Y/N) [2]",
    "W53": "AAM Resource Manpower/Shift/Cell", "X53": "AAM Resource Manpower/Shift/Cell [2]",
    "W54": "AAM Resource Floor Space (sq.m/Cell)", "X54": "AAM Resource Floor Space (sq.m/Cell) [2]",
    "AH36": "Material Handling in Machine Shop (₹)", "AE38": "Machining Cell Cycle Time (min)",
    "AI38": "Total Capital Expenditure (₹)",
    "AD42": "Cost of Cutting Tools (₹)", "AR42": "Cost of Cutting Tools [2] (₹)",
    "AD43": "Cost of Tool Holders (₹)", "AR43": "Cost of Tool Holders [2] (₹)",
    "AD44": "Cap Die Cost (₹)", "AR44": "Cost of Probing Unit (₹)",
    "AD45": "Cost of Fixtures (₹)", "AR45": "Cost of Fixtures [2] (₹)",
    "AD46": "Cost of Gauges (₹)", "AR46": "Cost of Gauges [2] (₹)",
    "AD47": "Cost of Material Handling (₹)", "AR47": "Cost of Material Handling [2] (₹)",
    "AD48": "CMM Fixture Cost (₹)", "AD49": "Coolant Oil Cost (₹)", "AR49": "Coolant Oil Cost [2] (₹)",
    "AD50": "DM Water Cost for Coolant (₹)", "AR50": "DM Water Cost for Coolant [2] (₹)",
    "AD51": "Barcode Label Cost (₹)", "AR51": "Barcode Label Cost [2] (₹)",
    "AD52": "Impregnation Basket Cost (₹)", "AR52": "Impregnation Basket Cost [2] (₹)",
    "S23": "Dressing Station (₹ Lac)", "S24": "Core Painting Station (₹ Lac)",
    "S25": "Core Handling Stand (₹ Lac)", "S26": "Core Cavity Handling Trolleys (₹ Lac)",
    "S27": "Core Visual Inspection / Table / Tools (₹ Lac)", "S28": "Vibro Decoring Hammer (₹ Lac)",
    "S29": "Vibro Decoring Fixture (₹ Lac)", "S30": "Casting Table (₹ Lac)",
    "S31": "Casting & Sand Collection Trolley (₹ Lac)", "S32": "Furnace Dross / Rejection Trolley & Ladle Set (₹ Lac)",
    "S33": "Cutting Fixture (₹ Lac)", "S34": "Riser Collection Trolley (₹ Lac)",
    "S35": "Fettling Table with Indexing Head (₹ Lac)", "S36": "Indexing Fixture (₹ Lac)",
    "S37": "Fettling Table (₹ Lac)", "S38": "Fettling Booth (₹ Lac)",
    "S39": "Cell Formation Cost (₹ Lac)", "S40": "Filing & Grinding Tools (₹ Lac)",
    "S41": "Final Inspection Table (₹ Lac)", "S42": "Storage Pallets (₹ Lac)",
    "S43": "Gauges — GDC (₹ Lac)", "Q44": "DM Water for Dycoat — Description",
    "S44": "DM Water for Dycoat (₹ Lac)", "Q45": "Shift Code Punching Fixture — Description",
    "S45": "Shift Code Punching Fixture (₹ Lac)", "S46": "Welding Booth (₹ Lac)",
    "S47": "Welding Fixture (₹ Lac)", "S48": "Fan for Operators (₹ Lac)",
    "S49": "Material Handling — Crates & Trolley (₹ Lac)", "S50": "Material Handling — Trolley Mould Type (₹ Lac)",
    "S51": "Profile Burner (₹ Lac)", "S52": "Others — Profile Filter (₹ Lac)",
    "S53": "Shot Blasting Hanger (₹ Lac)", "S54": "SS Shots for Volume (₹ Lac)",
    "S55": "HT Batch Code Punching Fixture (₹ Lac)", "S56": "HT Basket Cost (₹ Lac)",
    "S57": "Jet Cooling Cost (₹ Lac)", "S58": "Die Service Consumable (₹ Lac)",
    "S59": "Total Operating Investment (₹ Lac)",
    "K23": "Core Shooting M/c — Utilisation (%)", "L23": "Core Shooting M/c — Units", "M23": "Core Shooting M/c — Amount (₹ Lac)",
    "L24": "Core Painting Oven — Units", "M24": "Core Painting Oven — Amount (₹ Lac)",
    "K25": "Thermal Decoring M/c — Utilisation (%)", "L25": "Thermal Decoring M/c — Units", "M25": "Thermal Decoring M/c — Amount (₹ Lac)",
    "K26": "Crane to Handle Basket — Utilisation (%)", "L26": "Crane to Handle Basket — Units", "M26": "Crane to Handle Basket — Amount (₹ Lac)",
    "K27": "Vibro Decoring Machine — Utilisation (%)", "L27": "Vibro Decoring Machine — Units", "M27": "Vibro Decoring Machine — Amount (₹ Lac)",
    "K28": "Tilting Machine — Utilisation (%)", "L28": "Tilting Machine — Units", "M28": "Tilting Machine — Amount (₹ Lac)",
    "K29": "Vertical Machine — Utilisation (%)", "L29": "Vertical Machine — Units", "M29": "Vertical Machine — Amount (₹ Lac)",
    "K30": "Stand Type Machine — Utilisation (%)", "L30": "Stand Type Machine — Units", "M30": "Stand Type Machine — Amount (₹ Lac)",
    "K31": "Hydraulic Power Pack — Utilisation (%)", "L31": "Hydraulic Power Pack — Units", "M31": "Hydraulic Power Pack — Amount (₹ Lac)",
    "K32": "Holding Furnace — Utilisation (%)", "L32": "Holding Furnace — Units", "M32": "Holding Furnace — Amount (₹ Lac)",
    "K33": "Band Saw Machine — Utilisation (%)", "L33": "Band Saw Machine — Units", "M33": "Band Saw Machine — Amount (₹ Lac)",
    "K34": "Circular Saw Cutting Machine — Utilisation (%)", "L34": "Circular Saw Cutting Machine — Units", "M34": "Circular Saw Cutting Machine — Amount (₹ Lac)",
    "K35": "Knock Out Press — Utilisation (%)", "L35": "Knock Out Press — Units", "M35": "Knock Out Press — Amount (₹ Lac)",
    "K36": "Linishing Machine — Utilisation (%)", "L36": "Linishing Machine — Units", "M36": "Linishing Machine — Amount (₹ Lac)",
    "K37": "Shift Code Punching Machine — Utilisation (%)", "L37": "Shift Code Punching Machine — Units", "M37": "Shift Code Punching Machine — Amount (₹ Lac)",
    "K38": "Welding Machine — Utilisation (%)", "L38": "Welding Machine — Units", "M38": "Welding Machine — Amount (₹ Lac)",
    "J39": "Bend Removal Press — Description", "K39": "Bend Removal Press — Utilisation (%)",
    "L39": "Bend Removal Press — Units", "M39": "Bend Removal Press — Amount (₹ Lac)",
    "K40": "Robot Pouring & Extraction — Utilisation (%)", "L40": "Robot Pouring & Extraction — Units", "M40": "Robot Pouring & Extraction — Amount (₹ Lac)",
    "K41": "Endoscope Machine — Utilisation (%)", "L41": "Endoscope Machine — Units", "M41": "Endoscope Machine — Amount (₹ Lac)",
    "K42": "Special Core Handling/Testing — Utilisation (%)", "L42": "Special Core Handling/Testing — Units", "M42": "Special Core Handling/Testing — Amount (₹ Lac)",
    "K43": "Component Extractor/Catcher — Utilisation (%)", "L43": "Component Extractor/Catcher — Units", "M43": "Component Extractor/Catcher — Amount (₹ Lac)",
    "K44": "Air Balancer — Utilisation (%)", "L44": "Air Balancer — Units", "M44": "Air Balancer — Amount (₹ Lac)",
    "K45": "Core Painting Oven [2] — Utilisation (%)", "L45": "Core Painting Oven [2] — Units", "M45": "Core Painting Oven [2] — Amount (₹ Lac)",
    "K46": "Endoscope Machine [2] — Utilisation (%)", "L46": "Endoscope Machine [2] — Units", "M46": "Endoscope Machine [2] — Amount (₹ Lac)",
    "K47": "Deflashing Station — Utilisation (%)", "L47": "Deflashing Station — Units", "M47": "Deflashing Station — Amount (₹ Lac)",
    "K48": "Shot Blasting M/c — Utilisation (%)", "L48": "Shot Blasting M/c — Units", "M48": "Shot Blasting M/c — Amount (₹ Lac)",
    "K49": "Melting Furnace — Utilisation (%)", "L49": "Melting Furnace — Units", "M49": "Melting Furnace — Amount (₹ Lac)",
    "K50": "Melting Furnace Accessories — Utilisation (%)", "L50": "Melting Furnace Accessories — Units",
    "M50": "Melting Furnace Accessories — Amount (₹ Lac)",
    "K51": "Heat Treatment Furnace — Utilisation (%)", "L51": "Heat Treatment Furnace — Units", "M51": "Heat Treatment Furnace — Amount (₹ Lac)",
    "K52": "HT Batch Code Punching M/c — Utilisation (%)", "L52": "HT Batch Code Punching M/c — Units", "M52": "HT Batch Code Punching M/c — Amount (₹ Lac)",
    "K53": "Core Placement Fixture — Utilisation (%)", "L53": "Core Placement Fixture — Units", "M53": "Core Placement Fixture — Amount (₹ Lac)",
}

# Cells whose value is hardcoded or derived rather than read directly from a PDF cell.
CELL_SOURCE_TYPES: dict[str, str] = {
    "C10": "default",   # hardcoded "Domestic"
    "D10": "default",   # hardcoded "CIF"
    "G5": "derived",    # annual_volume_nos * 1.15
    "W29": "derived",   # boolean → Y/N
    "X29": "derived",
    "W33": "derived",
    "X33": "derived",
    "W52": "derived",
    "X52": "derived",
    "AI51": "derived",
}




