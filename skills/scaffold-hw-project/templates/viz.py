# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "trimesh", "rerun-sdk", "fast-simplification", "scipy"]
# ///
"""Visualization harness (rerun) — decimate, color, log, save.

METHODOLOGY / GOTCHAS (see GUARDRAILS.md, section 2):
  - `rr.save()` REPLACES the active sink: save the .rrd, THEN stream it into
    an open viewer (`uv run --with rerun-sdk python -m rerun out/<name>.rrd`).
    A viewer spawned BEFORE the save receives nothing.
  - Regeneration OVERWRITES the .rrd. Archive milestones to
    out/history/<date>/ BEFORE regenerating or the design history is lost.
  - EVERY rr.Mesh3D needs vertex_normals or it renders flat/unlit. Log
    trimesh's OWN .vertex_normals (process=False to keep hand-built arrays).
  - Voxel meshes are HUGE: decimate before logging. Decimation makes
    degenerate triangles -> NaNs in signed_distance; clean with
    update_faces(nondegenerate_faces()).
  - Ship an explicit blueprint; auto-layout makes empty-tab soup.
  - ONE .rrd PER CONCERN (design system vs each dynamic sim).

Run:   uv run viz.py
View:  uv run --with rerun-sdk python -m rerun out/model.rrd
"""
import datetime
import shutil
from pathlib import Path

import numpy as np
import trimesh
import rerun as rr
import rerun.blueprint as rrb

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
RRD = OUT / "model.rrd"
APP_ID = "project_model"
TARGET_TRIS = 200_000  # decimate voxel meshes down to this before logging


def archive_milestone():
    """Copy the previous .rrd to out/history/<date>/ before overwriting."""
    if RRD.exists():
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        dst = OUT / "history" / stamp
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RRD, dst / RRD.name)


def clean_mesh(m: trimesh.Trimesh) -> trimesh.Trimesh:
    m.update_faces(m.nondegenerate_faces())   # drop degenerate tris (NaN source)
    m.remove_unreferenced_vertices()
    return m


def decimate(m: trimesh.Trimesh, target=TARGET_TRIS) -> trimesh.Trimesh:
    if len(m.faces) > target:
        m = m.simplify_quadric_decimation(face_count=target)
    return clean_mesh(m)


def log_mesh(path: str, mesh: trimesh.Trimesh, color):
    """Log a mesh WITH vertex normals (mandatory) and a vertex color."""
    mesh = decimate(mesh)
    rr.log(path, rr.Mesh3D(
        vertex_positions=mesh.vertices,
        triangle_indices=mesh.faces,
        vertex_normals=mesh.vertex_normals,        # <- never omit this
        vertex_colors=np.tile(color, (len(mesh.vertices), 1)),
    ), static=True)


def main():
    archive_milestone()
    rr.init(APP_ID, spawn=False)
    rr.save(RRD)          # save FIRST; viewer is opened afterwards by the user

    # Load each exported mesh (out/*.stl/.ply) and log it. Example:
    stls = sorted(OUT.glob("*.stl"))
    palette = [(200, 80, 80), (80, 160, 200), (120, 200, 120), (210, 190, 90)]
    if not stls:
        # Fresh scaffold: log a placeholder box so the viewer isn't empty.
        box = trimesh.creation.box(extents=(1000, 200, 150))
        log_mesh("model/placeholder", box, palette[0])
    else:
        for i, f in enumerate(stls):
            log_mesh(f"model/{f.stem}", clean_mesh(trimesh.load(f)),
                     palette[i % len(palette)])

    # Explicit blueprint: one 3D view pointing at entities that exist.
    rr.send_blueprint(rrb.Blueprint(
        rrb.Spatial3DView(origin="/model", name="Model"),
        collapse_panels=True,
    ))
    print(f"wrote {RRD}\nview: uv run --with rerun-sdk python -m rerun {RRD}")


if __name__ == "__main__":
    main()
