---
name: continuum-fea
description: >-
  Run the continuum (tier-3) FEA on a part a beam model can't capture —
  bracket, fitting, lug, hull bottom panel, pressure shell, sponson root —
  with gmsh + CalculiX (ccx). Use when an audit's analytic check or the
  in-house beam FEA is too coarse and you need a real 3-D stress/displacement
  or buckling field. Drives the gmsh tet-mesh -> Abaqus .inp -> ccx ->
  parse -> VALIDATE-against-the-analytic-tier -> rerun pipeline, headless,
  from a uv single-file script. Refuses to trust a single mesh.
---

# Continuum FEA — gmsh + CalculiX (tier 3)

This is the heavy tier of the FEA ladder, used ONLY for continuum parts that
a beam or closed-form check can't represent:

```
tier 1  analytic checks in audit.py     (Euler buckling, beam bending, slam)  <- first
tier 2  in-house numpy space-frame FEA  (frames / trusses)
tier 3  THIS: gmsh + CalculiX (ccx)     (brackets, panels, shells, lugs)      <- last
```

**The solver is settled: CalculiX (`ccx`) + gmsh.** It is the OpenFOAM-of-FEA
for this stack — a turnkey, Abaqus-style **text-deck CLI** solver (not a
write-your-own-weak-forms framework), runs headless, and is already installed
(`/Applications/FreeCAD.app/Contents/Resources/bin/ccx`, v2.23, arm64). This
was confirmed by a sourced multi-methodology sweep (2026-06-13): ccx is the
robust pick across weighting schemes; Code_Aster / Elmer are escalation
options only if coupled multiphysics or advanced contact becomes load-bearing,
and both have a real macOS-install cost (Code_Aster has no turnkey
Apple-Silicon path; Elmer is Rosetta-source-build only).

## The discipline (this is the whole point)

A continuum solve that "ran clean" is **not** one that is correct — linear
tets lock, units slip, and a clamped BC invents a stress singularity, all
silently. So, exactly like CFD (`c*` / choked-mdot anchor + grid study):

1. **Validate tier 3 against the tier below FIRST.** Before you trust a
   result on the real part, solve a case with a closed-form answer and GATE
   on matching it: a cantilever whose tip deflection is `F·L³/3EI`, or — the
   canonical project anchor — a `*BUCKLE` step whose first eigenvalue must
   reproduce the audit's analytic Euler `P_cr` within a few percent. The
   scaffold ships `fea_continuum.py`, which does exactly this and exits 1 if
   the anchor misses.
2. **Then a mesh-convergence study.** Refine until the validated quantity
   stops moving (<~2-3%). One mesh is never a result. `log()` the sequence.
3. **Anchor the peak stress honestly.** A fully-clamped face has a stress
   singularity at its edge — peak von Mises will overshoot the nominal and
   will NOT converge there. Gate on a clean quantity (deflection, a
   `*BUCKLE` eigenvalue, or stress sampled away from the singularity); treat
   the raw peak as informational and say so.

## Procedure

1. **Get a meshable surface.** Raw PicoGK/voxel meshes are too dense and
   triangle-quality-poor for direct tet meshing (§6/§7). Either decimate the
   exported STL + let gmsh remesh it, or re-voxelize coarse (6-8 mm) and build
   hex (C3D8) directly for a topology-style check. Clean degenerate triangles
   (`m.update_faces(m.nondegenerate_faces())`).

2. **Mesh in gmsh, second order.** `gmsh.model.mesh.setOrder(2)` →
   **C3D10 quadratic tets** for bending. NEVER ship C3D4 linear tets for a
   bending part — they shear-lock and silently under-predict (§7). Mind the
   gmsh→Abaqus tet10 node-order permutation (swap the last two mid-edge
   nodes) — get it wrong and ccx throws a negative Jacobian or the anchor
   fails loudly (that's the guardrail working).

3. **Write the `.inp` deck** with an explicit unit system in the header —
   CalculiX is **unit-agnostic** (`N, mm, MPa, tonne, t/mm³` is the safe set;
   mm geometry + `E` in Pa silently scales stress by 10^x, §7). Keys:
   `*NODE`, `*ELEMENT,TYPE=C3D10`, `*MATERIAL/*ELASTIC`, `*SOLID SECTION`,
   `*BOUNDARY`, `*CLOAD`/`*DLOAD`, and a step: `*STATIC`, `*BUCKLE`, or
   `*FREQUENCY`. Request `*NODE PRINT U` + `*EL PRINT S` (whitespace `.dat`,
   easy to parse) and/or `*NODE FILE`/`*EL FILE` (`.frd` field for viz).

4. **Run headless.** `subprocess.run([CCX, "-i", job])`. The solver is pure
   CLI — **never** depend on `cgx`/GraphiX (it needs XQuartz); parse the
   results and visualize in rerun (§7).

5. **Parse + validate + gate.** Parse `.dat` for the validated scalar(s),
   compare to the analytic anchor, PASS/WARN/FAIL, exit 1 on FAIL — same
   contract as `audit.py`. Add the buckling/stress margin as a scored check
   in `audit.py` via `add-scored-audit` so it can't silently regress.

6. **Visualize.** Log the mesh / deformed shape colored by von Mises or |U|
   to its own `.rrd` (one concern per file; `vertex_normals` on every mesh;
   `rr.save()` then stream into the viewer — §2). Look at it, including the
   region you loaded.

## Install / pin

- Already present: FreeCAD's bundled `ccx` 2.23 (zero-effort, the default).
- Reproducible CI pin: `conda install -c conda-forge calculix` (osx-arm64
  2.23). Don't assume install paths agree — the costerwi Homebrew tap tracks
  ~2.22 (§7 version-drift).
- gmsh via the pip/uv wheel (PEP 723 `dependencies = ["gmsh", ...]`).

## Anti-patterns to reject

- Trusting a continuum result that was never checked against the analytic
  tier or a single mesh ("it ran" ≠ "it's right").
- C3D4 linear tets on a bending part (locks; under-predicts silently).
- Hard-coding a geometry constant in the deck instead of reading
  `design/design.json` / the exported artifact.
- A `*BUCKLE` `P_cr` or stress margin that never makes it back into
  `audit.py` as a scored, gating check.
- Depending on `cgx` for post-processing in a headless/CI run.
- A mixed unit system, or an `.inp` with no stated units.
