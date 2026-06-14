---
name: import-cad
description: >-
  Bring an EXISTING CAD file (STEP/.stp, or STL/OBJ/GLB/PLY mesh) into the
  hardware-as-code pipeline so it can be verified and simulated — the
  "I already have the CAD" path, as opposed to authoring geometry as code. Use
  when the user provides a CAD/mesh file and wants audits, FEA, CFD, mass/CG,
  clearances, or rerun viz on it. Loads the file, converts to canonical mm,
  computes the artifacts the audits expect (out/imported.json + a mesh), and
  wires up materials for mass. Handles the units / watertight / native-format
  traps. STEP needs build123d (OCCT); native formats must be exported to STEP/STL.
---

# import-cad

The plugin has two doors. The default is **geometry-as-code** (author
`design.json`, a kernel builds it). This is the **other** door: the user already
has a CAD file and wants to *verify and simulate* it.

## When to use

The user hands you a `.step/.stp`, `.stl`, `.obj`, `.glb`, or `.ply` and asks to
check / analyze / simulate / measure it. (Native CAD — `.sldprt`, Fusion,
CATIA, Inventor — can't be read; ask them to export STEP or STL first.)

## Procedure

1. Run the importer (template: `import_cad.py`):
   ```bash
   # mesh:
   uv run import_cad.py part.stl --units mm --material Al-6061-T6
   # STEP (exact BREP) needs OCCT:
   uv run --with build123d import_cad.py part.step --units mm --material Al-6061-T6
   ```
   It writes `out/imported.json` (bbox, volume, centroid, mass, watertight,
   warnings) + `out/imported_mesh.ply`.
2. **Confirm `--units` and SANITY-CHECK the printed bbox** against the real part.
   STL is unitless and STEP units are often wrong; a 25.4x or 1000x scale error
   silently corrupts everything. Do not proceed on a bbox that looks wrong.
3. **Assign a material** (`--material`, resolved from `design/materials.json`)
   so mass is real — never invent a density. If the material isn't in the file,
   add it first with the **add-material** skill (cited).
4. If the mesh is **not watertight**, volume/mass/FEA are unreliable — repair it
   (or use the STEP/BREP, which carries an exact volume) before trusting numbers.
5. Now run the rest on the imported geometry:
   - **add-scored-audit** — write checks that read `out/imported.json` /
     `out/imported_mesh.ply` (bbox, mass budget, clearances, wall thickness).
   - **fea_continuum** — gmsh meshes the STEP/STL directly → CalculiX.
   - **viz.py** — rerun the imported mesh.
   - **run-tradeoff-study** — compare variants if you have several files.
6. Treat `design.json` as the **requirements/targets ledger** here (anchors,
   allowables, mass/CG targets) even though it no longer *generates* the
   geometry — so the scored-audit discipline still applies.

## Gotchas (see GUARDRAILS §9)

- **Units** are the #1 silent killer — require and verify them.
- **Mass** needs a cited density (materials.json); leave it null otherwise.
- **Watertightness** gates volume and FEA; flag and fix.
- **STEP** = exact BREP (preferred: real volume, re-meshable); **STL/mesh** =
  tessellated approximation (no exact volume unless watertight).
- **Native formats** aren't supported — export to STEP/STL first.
