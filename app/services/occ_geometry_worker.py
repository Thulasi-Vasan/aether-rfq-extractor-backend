from __future__ import annotations

import json
import sys
from pathlib import Path

from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopAbs import TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer


def solid_count(shape: object) -> int:
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def extract_geometry(path: Path) -> dict[str, object]:
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise ValueError("OpenCascade could not read the STEP file.")
    reader.TransferRoots()
    shape = reader.OneShape()

    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)
    x_min, y_min, z_min, x_max, y_max, z_max = bbox.Get()

    volume_props = GProp_GProps()
    brepgprop_VolumeProperties(shape, volume_props)

    surface_props = GProp_GProps()
    brepgprop_SurfaceProperties(shape, surface_props)

    return {
        "bounding_box_mm": {
            "x_min": round(float(x_min), 6),
            "y_min": round(float(y_min), 6),
            "z_min": round(float(z_min), 6),
            "x_max": round(float(x_max), 6),
            "y_max": round(float(y_max), 6),
            "z_max": round(float(z_max), 6),
            "length": round(float(x_max - x_min), 6),
            "width": round(float(y_max - y_min), 6),
            "height": round(float(z_max - z_min), 6),
        },
        "volume_mm3": round(float(volume_props.Mass()), 6),
        "surface_area_mm2": round(float(surface_props.Mass()), 6),
        "solid_count": solid_count(shape),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: occ_geometry_worker.py <step-path>"}), file=sys.stderr)
        return 2

    try:
        payload = extract_geometry(Path(sys.argv[1]))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
