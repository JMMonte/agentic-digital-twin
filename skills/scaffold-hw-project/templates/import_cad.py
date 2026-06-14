# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "trimesh", "fast-simplification"]
# ///
"""Import an EXISTING CAD file into the hardware-as-code pipeline.

The plugin's default door is geometry-as-code (design.json -> build -> out/*.json).
This is the OTHER door: you already have a CAD file and want to verify / simulate
it. It loads the file, computes the artifacts the audits expect, and writes them
to out/ so add-scored-audit / fea_continuum / viz / add-material all run on it.

  uv run import_cad.py <file.step|.stl|.obj|.glb|.ply> --units mm [--material <key>]

  STEP/.stp (exact BREP) needs build123d (OCCT):
      uv run --with build123d import_cad.py part.step --units mm --material Al-6061-T6
  Meshes (.stl/.obj/.glb/.ply) use trimesh only — no extra deps.
  Native formats (.sldprt, Fusion, CATIA, ...) are NOT readable — export to STEP/STL first.

GOTCHAS (also in GUARDRAILS):
- UNITS: STL is UNITLESS and STEP units are easy to get wrong. You MUST pass
  --units; everything is converted to mm. A 25.4x or 1000x scale error silently
  wrecks every downstream number — this script prints the bbox so you can sanity it.
- MASS needs a density: pass --material <key> (looked up in design/materials.json).
  Without it, mass is left null and flagged — never invent one.
- VOLUME / FEA need a watertight solid. A non-watertight mesh gets volume=null +
  a warning (repair the mesh, or use the STEP/BREP).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}


def load_as_mesh(path: Path):
    ext = path.suffix.lower()
    if ext in (".step", ".stp"):
        try:
            from build123d import import_step, export_stl
        except ImportError:
            sys.exit("STEP needs build123d (OCCT). Re-run:\n"
                     f"  uv run --with build123d import_cad.py {path.name} --units mm ...")
        part = import_step(str(path))
        tmp = OUT / "_brep_tess.stl"
        export_stl(part, str(tmp), tolerance=0.1, angular_tolerance=0.3)
        mesh = trimesh.load(tmp, force="mesh")
        tmp.unlink(missing_ok=True)
        return mesh, "brep(step)", float(part.volume)   # exact BREP volume (in the file's units)
    if ext in (".stl", ".obj", ".glb", ".gltf", ".ply"):
        return trimesh.load(path, force="mesh"), f"mesh({ext[1:]})", None
    sys.exit(f"Unsupported format '{ext}'. Export native CAD to STEP or STL first.")


def density_kg_m3(material: str | None):
    if not material:
        return None, "no --material given; mass left null (assign a material via add-material)"
    mpath = ROOT / "design" / "materials.json"
    if not mpath.exists():
        return None, f"design/materials.json not found; cannot resolve '{material}'"
    mats = json.loads(mpath.read_text()).get("materials", {})
    if material not in mats:
        return None, f"'{material}' not in materials.json (add it via add-material, with a citation)"
    d = mats[material].get("density_kg_m3")
    return d, (None if d else f"'{material}' has no density_kg_m3")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--units", default=None, choices=list(UNIT_TO_MM),
                    help="REQUIRED: source units (mm/cm/m/in/ft). STL is unitless; STEP is often wrong.")
    ap.add_argument("--material", default=None, help="key in design/materials.json (for mass)")
    a = ap.parse_args()

    path = Path(a.file)
    if not path.exists():
        sys.exit(f"file not found: {path}")
    if a.units is None:
        sys.exit("--units is REQUIRED (mm/cm/m/in/ft). Confirm the file's real units; "
                 "a wrong guess silently breaks every downstream number.")

    mesh, kind, brep_volume = load_as_mesh(path)
    scale = UNIT_TO_MM[a.units]
    mesh.apply_scale(scale)                      # -> mm
    warnings = []

    watertight = bool(mesh.is_watertight)
    if brep_volume is not None:
        volume_mm3 = brep_volume * scale ** 3    # exact BREP volume, scaled
    elif watertight:
        volume_mm3 = float(mesh.volume)
    else:
        volume_mm3 = None
        warnings.append("mesh is NOT watertight -> volume/mass/FEA unreliable; repair it or use the STEP/BREP")

    centroid = (mesh.center_mass if watertight else mesh.centroid).tolist()
    lo, hi = mesh.bounds
    rho, mat_note = density_kg_m3(a.material)
    if mat_note:
        warnings.append(mat_note)
    mass_kg = (volume_mm3 * 1e-9 * rho) if (volume_mm3 and rho) else None

    # decimated mesh for viz / quick audits
    viz = mesh
    if len(mesh.faces) > 200_000:
        import fast_simplification
        v, f = fast_simplification.simplify(np.asarray(mesh.vertices, np.float32),
                                            np.asarray(mesh.faces, np.int64), target_count=120_000)
        viz = trimesh.Trimesh(v, f)
    viz.export(OUT / "imported_mesh.ply")

    artifact = {
        "source_file": str(path), "kind": kind, "declared_units": a.units, "units": "mm (canonical)",
        "watertight": watertight,
        "bbox_min_mm": [round(float(x), 3) for x in lo],
        "bbox_max_mm": [round(float(x), 3) for x in hi],
        "bbox_size_mm": [round(float(x), 3) for x in (hi - lo)],
        "centroid_mm": [round(float(x), 3) for x in centroid],
        "volume_mm3": round(volume_mm3, 1) if volume_mm3 else None,
        "material": a.material, "density_kg_m3": rho,
        "mass_kg": round(mass_kg, 4) if mass_kg else None,
        "mesh": "out/imported_mesh.ply", "triangles": int(len(mesh.faces)),
        "warnings": warnings,
        "_note": "Geometry imported, NOT code-defined. Audits/FEA/viz read these. "
                 "VERIFY bbox_size_mm against the real part — if it's off by ~25.4x or 1000x, fix --units.",
    }
    (OUT / "imported.json").write_text(json.dumps(artifact, indent=2))

    print(f"imported {path.name}  [{kind}]  units={a.units}->mm")
    print(f"  bbox  {artifact['bbox_size_mm']} mm   (SANITY-CHECK this against the real part)")
    print(f"  vol   {artifact['volume_mm3']} mm^3   watertight={watertight}")
    print(f"  mass  {artifact['mass_kg']} kg   (material={a.material}, rho={rho})")
    print(f"  -> out/imported.json + out/imported_mesh.ply")
    for w in warnings:
        print(f"  WARN: {w}")


if __name__ == "__main__":
    main()
