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




