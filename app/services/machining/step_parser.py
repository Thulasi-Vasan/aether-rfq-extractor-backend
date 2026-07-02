"""STEP -> feature summary using pythonOCC (OpenCASCADE).

This is intentionally a small, well-bounded summary: bounding box, volume,
estimated weight, and face-type counts (cylindrical bores, planar faces, etc.)
plus a histogram of cylindrical-face radii (hint at hole/bore sizes). That is
high-signal, low-token context for the LLM — far better than dumping raw STEP.

The extraction is isolated behind `summarize_step()` so it can be swapped for a
deeper feature recognizer later without touching the rest of the agent.

Requires the `cad-occ` conda env (pythonocc-core is conda-only, not pip).
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from app.models import StepFeatureSummary

log = logging.getLogger(__name__)


def _load_occ() -> tuple[Any, ...]:
    try:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Extend.DataExchange import read_step_file
    except ImportError as exc:
        raise RuntimeError(
            "pythonOCC is required when ENABLE_OCC=true. Install pythonocc-core in the "
            "cad-occ conda env, or set ENABLE_OCC=false and optionally USE_STATIC_SUMMARY=true."
        ) from exc
    return (
        Bnd_Box,
        BRepAdaptor_Surface,
        brepbndlib,
        brepgprop,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GProp_GProps,
        TopAbs_FACE,
        TopAbs_SOLID,
        TopExp_Explorer,
        read_step_file,
    )


def _count_solids(shape: Any, top_exp_explorer: Any, top_abs_solid: Any) -> int:
    n = 0
    exp = top_exp_explorer(shape, top_abs_solid)
    while exp.More():
        n += 1
        exp.Next()
    return n


def summarize_step(step_path: str, density_g_per_mm3: float) -> StepFeatureSummary:
    """Read a STEP file and return a compact geometric feature summary."""
    (
        Bnd_Box,
        BRepAdaptor_Surface,
        brepbndlib,
        brepgprop,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GProp_GProps,
        TopAbs_FACE,
        TopAbs_SOLID,
        TopExp_Explorer,
        read_step_file,
    ) = _load_occ()

    log.info("pythonOCC: reading STEP file %s", step_path)
    shape = read_step_file(step_path)

    # Bounding box (sorted descending so it reads like L x B x H).
    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    dims = sorted([xmax - xmin, ymax - ymin, zmax - zmin], reverse=True)
    bbox = [round(d, 1) for d in dims]

    # Volume + estimated weight.
    props = GProp_GProps()
    brepgprop.VolumeProperties(shape, props)
    volume = props.Mass()  # for VolumeProperties this is volume in mm^3
    weight_kg = round(volume * density_g_per_mm3 / 1000.0, 3)

    # Face-type breakdown + cylinder radius histogram.
    counts = Counter()
    radii: Counter = Counter()
    faces = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        faces += 1
        surf = BRepAdaptor_Surface(exp.Current())
        stype = surf.GetType()
        if stype == GeomAbs_Cylinder:
            counts["cyl"] += 1
            r = surf.Cylinder().Radius()
            radii[f"{round(r * 2) / 2:.1f}"] += 1  # round Ø-driving radius to 0.5 mm
        elif stype == GeomAbs_Plane:
            counts["plane"] += 1
        elif stype == GeomAbs_Cone:
            counts["cone"] += 1
        else:
            counts["other"] += 1
        exp.Next()

    summary = StepFeatureSummary(
        bounding_box_mm=bbox,
        volume_mm3=round(volume, 0),
        estimated_weight_kg=weight_kg,
        num_solids=_count_solids(shape, TopExp_Explorer, TopAbs_SOLID),
        num_faces=faces,
        num_cylindrical_faces=counts["cyl"],
        num_planar_faces=counts["plane"],
        num_conical_faces=counts["cone"],
        num_freeform_faces=counts["other"],
        cylinder_radius_histogram_mm=dict(sorted(radii.items(), key=lambda kv: float(kv[0]))),
    )
    log.info(
        "pythonOCC: bbox=%s mm  weight=%.3f kg  faces=%d (cyl=%d plane=%d cone=%d freeform=%d)",
        "x".join(str(d) for d in summary.bounding_box_mm),
        summary.estimated_weight_kg,
        summary.num_faces,
        summary.num_cylindrical_faces,
        summary.num_planar_faces,
        summary.num_conical_faces,
        summary.num_freeform_faces,
    )
    return summary


def summary_to_prompt_text(s: StepFeatureSummary) -> str:
    """Render the feature summary as compact text for the LLM user message."""
    hist = ", ".join(f"R{r}mm x{n}" for r, n in s.cylinder_radius_histogram_mm.items()) or "none"
    return (
        "3D STEP feature summary:\n"
        f"- Bounding box (L x B x H): {s.bounding_box_mm[0]} x {s.bounding_box_mm[1]} "
        f"x {s.bounding_box_mm[2]} mm\n"
        f"- Volume: {s.volume_mm3:.0f} mm^3; estimated weight: {s.estimated_weight_kg} kg\n"
        f"- Solids: {s.num_solids}; total faces: {s.num_faces}\n"
        f"- Face types: {s.num_cylindrical_faces} cylindrical (bores/turning candidates), "
        f"{s.num_planar_faces} planar, {s.num_conical_faces} conical, "
        f"{s.num_freeform_faces} freeform\n"
        f"- Cylindrical-face radii (hole/bore size hints): {hist}\n"
    )
