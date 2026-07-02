"""Fixed machine / work-center inventory.

The LLM must select `operation_name` from this list when it is populated. This is
the single source of truth for machine names used by the tool schema, prompt,
and backend validation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MachineSpec:
    """Generic machine/work-center metadata used only for prompt guidance."""

    name: str
    process_type: str
    capabilities: tuple[str, ...] = ()
    capacity: str | None = None
    selection_notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


MACHINE_SPECS: tuple[MachineSpec, ...] = (
    # Turning centers
    MachineSpec(
        name="TURNING CENTER- Diffuser & Inlet M/cng (LT-20)",
        process_type="turning",
        capabilities=("diffuser-side turning", "inlet-side turning", "boring", "facing"),
        selection_notes=("Use for rotational features on the diffuser/inlet side.",),
    ),
    MachineSpec(
        name="TURNING CENTER- Outlet M/cng- SMALL, MEDIUM (LT-20)",
        process_type="turning",
        capabilities=("outlet-side turning", "boring", "facing"),
        selection_notes=("Use for rotational outlet-side features on small or medium parts.",),
    ),
    # VMC / machining centers
    MachineSpec(
        name="VMC 450 & 5th AXIS - WTH ROTARY TABLE, XYZ600x450x500, TS-900 X 450",
        process_type="milling",
        capabilities=("5-axis machining", "milling", "drilling", "tapping", "multi-angle access", "setup consolidation"),
        capacity="XYZ 600x450x500, table 900x450",
        selection_notes=(
            "Use when the operation requires 5-axis machining capability or multi-angle access consolidates machining-center work into one setup.",
        ),
    ),
    MachineSpec(
        name="Fanuc robo drill Alpha-D21LiB Plus - X-700x400x330 GPL 150 to 480 Table 850x410 Rpm 10000 Rapid 482/min (21tools) tool",
        process_type="milling",
        capabilities=("drilling", "tapping", "light milling"),
        capacity="X700 Y400 Z330, table 850x410",
        selection_notes=("Use when drilling, tapping, or light milling is a standalone setup.",),
        limitations=("Do not split from another machining-center setup that can complete the same holes or taps.",),
    ),
    MachineSpec(
        name="MCV 650 -XYZ -1200/650/960, Table size 1200x650,Rapid,32/32/24,Rpm std 6000 / opt12000 Tools-24/30/40 M/c-",
        process_type="milling",
        capabilities=("vertical milling", "drilling", "boring"),
        capacity="XYZ 1200x650x960, table 1200x650",
    ),
    MachineSpec(
        name="VMC 450 & 4th AXIS - XYZ-600x450x500, TS-900 X 450",
        process_type="milling",
        capabilities=("4-axis indexed machining", "milling", "drilling", "tapping"),
        capacity="XYZ 600x450x500, table 900x450",
        selection_notes=("Use for features that can be reached by indexed rotation around one axis.",),
    ),
    MachineSpec(
        name="BFW- Orion-H6600-4 th Axis -X/Y/Z-1000x1000x1000, Table 20 Size - 630x630,Chip to chip -4.2, tool to tool -2.0",
        process_type="milling",
        capabilities=("4-axis indexed machining", "milling", "drilling", "boring"),
        capacity="XYZ 1000x1000x1000, table 630x630",
    ),
    MachineSpec(
        name="VMC 700 & 4th AXIS - XYZ-1500x700x700, TS-1650 X 700 , BT-40, Spindle Speed 5K (Opt-8)Rapid-20/20/20m/min)",
        process_type="milling",
        capabilities=("4-axis indexed machining", "milling", "drilling", "boring"),
        capacity="XYZ 1500x700x700, table 1650x700",
    ),
    MachineSpec(
        name="VMC 450 & 4th AXIS - XYZ-800x450x500, TS-1000 X 450 , BT-40, Spindle Speed 6K (Opt-10K)Rapid-36m/min )",
        process_type="milling",
        capabilities=("4-axis indexed machining", "milling", "drilling", "tapping"),
        capacity="XYZ 800x450x500, table 1000x450",
    ),
    # Specialist machines
    MachineSpec(
        name="DEEP HOLE DRILLING MACHINE, LENGTH ABOVE 300 MM",
        process_type="drilling",
        capabilities=("deep hole drilling",),
        capacity="hole length above 300 mm",
    ),
    # Post-machining stations
    MachineSpec(
        name="DRY CUM WET LEAK TEST",
        process_type="testing",
        capabilities=("dry leak test", "wet leak test"),
    ),
    MachineSpec(
        name="FINAL INSPECTION USING CMM",
        process_type="inspection",
        capabilities=("dimensional inspection", "GD&T verification", "final inspection"),
    ),
    MachineSpec(
        name="ENDOSCOPE STATION",
        process_type="inspection",
        capabilities=("internal visual inspection", "burr inspection", "passage inspection"),
    ),
    # Washing / cleaning
    MachineSpec(
        name="WASHING MACHINE - SMALL, BELOW 250 MM",
        process_type="cleaning",
        capabilities=("washing", "chip and coolant removal"),
        capacity="part size below 250 mm",
    ),
    MachineSpec(
        name="WASHING MACHINE - MEDIUM, BTW. 250 TO 500 MM",
        process_type="cleaning",
        capabilities=("washing", "chip and coolant removal"),
        capacity="part size between 250 and 500 mm",
    ),
    MachineSpec(
        name="WASHING MACHINE - LARGE, ABOVE 500 MM",
        process_type="cleaning",
        capabilities=("washing", "chip and coolant removal"),
        capacity="part size above 500 mm",
    ),
    MachineSpec(
        name="ULTRASONIC CLEANING EQUIPMENT",
        process_type="cleaning",
        capabilities=("ultrasonic cleaning", "fine contamination removal"),
    ),
    # Marking
    MachineSpec(
        name="LASER MARKING USING 2D SCANNER",
        process_type="marking",
        capabilities=("laser marking", "2D code marking", "part identification"),
    ),
    MachineSpec(
        name="INKJET MARKING",
        process_type="marking",
        capabilities=("inkjet marking", "part identification"),
    ),
    MachineSpec(
        name="CHEMICAL ETCHING/ ELECTROCHEMICAL MARKING",
        process_type="marking",
        capabilities=("chemical etching", "electrochemical marking", "part identification"),
    ),
)

MACHINE_INVENTORY: list[str] = [machine.name for machine in MACHINE_SPECS]


def _join_items(items: tuple[str, ...]) -> str:
    return "; ".join(items)


def inventory_as_prompt_block() -> str:
    """Render machine names and generic metadata for the system prompt."""
    lines: list[str] = []
    for machine in MACHINE_SPECS:
        lines.append(f"- {machine.name}")
        lines.append(f"  Process: {machine.process_type}")
        if machine.capabilities:
            lines.append(f"  Capabilities: {_join_items(machine.capabilities)}")
        if machine.capacity:
            lines.append(f"  Capacity: {machine.capacity}")
        if machine.selection_notes:
            lines.append(f"  Selection notes: {_join_items(machine.selection_notes)}")
        if machine.limitations:
            lines.append(f"  Limitations: {_join_items(machine.limitations)}")
    return "\n".join(lines)
