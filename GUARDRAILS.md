# GUARDRAILS.md — the living gotcha checklist

> This is the HOME for "things that silently gave a wrong answer." It is
> designed to be APPENDED to forever. Every time a sim, audit, build, or
> tradeoff lies to you and you figure out why, add a one-paragraph entry
> here under the right section, dated, with the symptom and the fix. New
> lessons go at the TOP of their section (newest first). Do not delete old
> entries — strike through with `~~...~~` and note the supersession if one
> is obsolete.
>
> Skills in this plugin (`guardrails-check`, `add-scored-audit`,
> `run-tradeoff-study`, `manufacturability-loop`, `scaffold-hw-project`)
> all point back here. When you scaffold a new project, this file is copied
> in so the project's own lessons live beside its code.

The meta-rule behind all of these: **a result that "ran clean" is not a
result that is correct.** Voxel kernels, CFD configs, and `np.interp` all
fail SILENTLY — the worst failure mode for an agent, because there is no
exception to catch. Every derived number must be cross-checked against an
independent anchor (analytic formula, published spec, or the REAL exported
artifact) before you trust it.

---

## 0. The first principles (read before anything)

1. **Spec/geometry is code.** ONE source-of-truth `design.json`. The build
   source (e.g. `Design.cs`) MIRRORS it — update the JSON first, then the
   mirror, never one without the other. Published/measured values are
   tagged `[PUB]`; everything else is DERIVED and must trace back to an
   anchor. Never present a derived number as if it were published.
2. **Every requirement gets an executable, scored audit.** PASS / WARN /
   FAIL, exit 1 on any FAIL, markdown report artifact. Audits read the
   build's exported JSON artifacts. They NEVER duplicate a geometry
   constant — regex it out of the source or read the JSON.
3. **Cheapest fidelity that discriminates.** Resolve a design fork with a
   placement-level scored study before you spend a full build/sim on it.
   Only the winner earns the expensive verification.
4. **Look at the render.** Every change ends with a visualization you
   actually open — including the underside and any region you touched.
   "The audit passed" is necessary, not sufficient.

---

## 1. Silent-failure traps (the GOLD section)

- **A wrong boolean still passes `watertight` and `volume > 0`.** A failed
  subtract, a flood-filled cavity, or a part union that quietly did nothing
  all produce a closed, positive-volume mesh. Watertightness checks CANNOT
  catch them (voxel meshes are always closed). FIX: every audit must assert
  the EXPECTED bbox / volume / CG against a known value, not just "> 0".
- **`np.interp` requires ASCENDING `xp`.** For a "lower is better" metric,
  use ascending `xp` with REVERSED `fp` — e.g.
  `np.interp(Iyy, [lo, hi], [5, 2])`. A descending `xp` does not raise; it
  silently INVERTS the metric (this once made the worst layout score best
  on takeoff). Whenever you map a physical value to a score, write down
  which direction is better and check a hand value at each end.
- **Sanity-check derived metrics against the REAL exported artifact, not an
  assumed envelope.** "It should be roughly a box this big" is how you get
  a side pack that pokes out the hull's tumblehome top corner. Integrate
  against the actual exported ring / section / mesh.
- **Voxel kernels fail SILENTLY (worst case for agents).** Enclosed voids
  are impossible: a `BoolSubtract` with a fully-enclosed cutter is a no-op,
  and a carved void floods back if a later `BoolAdd` seals its opening.
  Rule: **union first, subtract last, vent every cavity to the exterior.**
  Keep voxel artifacts OFF the outer mold line — a sub-voxel wall reads as
  closed even when it is physically open (the step-face trap).
- **Pin the loft direction.** When lofting between two profiles, set
  `ruled=` explicitly. The default can twist or fan the surface in a way
  that looks plausible in one view and is wrong in another.
- **CFD `FLUID_MODEL` defaults to STANDARD_AIR / ideal-gas traps.** SU2
  silently ignores `GAMMA_VALUE` / `GAS_CONSTANT` unless you set
  `FLUID_MODEL= IDEAL_GAS`. Symptom: the field decodes to an impossible
  Mach for your gamma. Always validate CFD against an analytic anchor
  (c\*, choked mdot) AND a grid-convergence study before trusting it.

---

## 2. Visualization (rerun) gotchas

- `rr.save()` REPLACES the active sink — a viewer spawned before the save
  gets nothing logged after it. Pattern: `rr.save()` the `.rrd`, THEN
  stream it into an open viewer (`python -m rerun out/x.rrd`).
- Regeneration OVERWRITES `.rrd` files. Archive milestones to
  `out/history/<date-rev>/` BEFORE regenerating, or the design evolution is
  lost.
- EVERY `rr.Mesh3D` needs `vertex_normals` or it renders flat / unlit. Use
  trimesh's own `.vertex_normals`; for flat quads pass `[[0,0,1]]*4`.
- Ship an explicit blueprint (`rr.send_blueprint`) — auto-layout makes
  empty-tab soup. Every view must point at an entity that exists.
- Keep separate concerns in separate `.rrd` files (design system vs each
  dynamic sim) so one does not overwrite the other.
- One `Spatial3DView` PER candidate, tiled, is the canonical
  side-by-side-comparison UX (do not overwrite one recording per rev).

---

## 3. Verification-ladder gotchas

- Assembly check = atomic components → pairwise voxel intersections →
  contact graph → union-find single-island. This catches floating parts,
  plane-touching joints, and failed booleans that volume checks miss.
- Model joints as components (clevis / pin / boss) so the load path is
  verified. Pin joints INTERPENETRATE — a clearance fit reads as ZERO
  contact in voxels, so give articulating interfaces a modeled clearance or
  the graph shows a false rigid link.
- Mechanism sweeps: rotate analytic points / rigid meshes through the
  range. EXCLUDE fitting zones near hinges. NEVER rigidly rotate an
  articulating member with the body — that's false interference.

---

## 4. Tradeoff-study gotchas

- See the `np.interp` trap in §1 — it is the #1 study killer.
- Score the thing that actually constrains, not a proxy that looks placed:
  e.g. pack DENSITY (kg/L) catches a box too small to hold its cells.
- Run a SENSITIVITY sweep across weight schemes and pick the ROBUST option,
  not the winner of one weighting. A single weighting hides ties and
  fragile leads.
- Evaluate candidates at the cheapest fidelity that DISCRIMINATES. If a
  metric is ~constant across candidates (e.g. CG_x when payload sits at the
  CG), it does not earn a column — drop it and find one that separates.

---

## 5. Simulation / dynamics gotchas

- Sign conventions are the #1 dynamics bug. Write down the sign of every
  control derivative and add a runtime self-check (e.g. animated surface
  normal vs commanded boresight < 0.5°). The first autopilot flew into the
  water because positive elevator = nose-DOWN was not negated.
- Calibrate each subsystem OPEN-LOOP against independent truth BEFORE
  closing the loop. Integrated runs hide subsystem defects as "noise."
- Index traps in state vectors are silent: feeding `w` (state[5]) to a
  sideslip PID that wanted `v` (state[4]) gave 16° sideslip and zero
  completed legs. Name your state slices.
- Clear cached intermediate artifacts (sliced sim parts, remeshes) after a
  rebuild that changes a moving part, or you visualize stale geometry.

---

## 6. Mesh hygiene

- Voxel meshes are huge — decimate before viz/queries.
- Decimation creates degenerate triangles → NaNs in
  `trimesh.proximity.signed_distance`. Clean with
  `m.update_faces(m.nondegenerate_faces())` and use `np.nanmax`.

---

## 7. FEA (gmsh + CalculiX) gotchas

The continuum tier (tier 3) is **gmsh + CalculiX (`ccx`)** — a turnkey,
Abaqus-style `.inp` CLI solver, already bundled with FreeCAD (v2.23). Same
meta-rule: a solve that "ran" is not one that is correct.

- **Validate tier 3 against the analytic tier BEFORE trusting it.** A
  `*BUCKLE` step's first eigenvalue must reproduce the audit's analytic Euler
  `P_cr` within a few percent (the strut anchor), or a cantilever's tip
  deflection must match `F·L³/3EI` — THEN run a mesh-convergence study. One
  mesh is never a result; refine until the validated quantity stops moving
  (<~2-3%). Same discipline as CFD's c\*/choked-mdot anchor + grid study.
- **C3D10 (quadratic tet) for bending, NEVER C3D4 (linear tet).** Linear tets
  shear-lock — over-stiff, SILENTLY under-predicting deflection and stress.
  Use `gmsh.model.mesh.setOrder(2)`. For topology-style checks build C3D8 hex
  directly from a coarse (6-8 mm) re-voxelization.
- **The gmsh→Abaqus tet10 node order differs.** Corners match; the last two
  mid-edge nodes are swapped (`abaqus = gmsh[:8] + [gmsh[9], gmsh[8]]`). Wrong
  ordering → a ccx negative-Jacobian error or a garbage field — which the
  analytic anchor catches LOUDLY. This permutation IS a guardrail; keep it.
- **CalculiX is unit-AGNOSTIC.** Pick ONE consistent system (safe:
  `N, mm, MPa, tonne, t/mm³`) and STATE it in the `.inp` heading. mm geometry
  with `E` in Pa silently scales every stress by 10^x. End every run by
  asserting a known closed-form value, not eyeballing the field.
- **A clamped face invents a stress singularity at its edge.** Peak von Mises
  there OVERSHOOTS the nominal and will NOT converge under refinement. Don't
  gate on it — gate on a clean quantity (deflection, a `*BUCKLE` eigenvalue,
  or stress sampled away from the singularity) and label the raw peak
  informational.
- **Raw PicoGK/voxel meshes are too dense and triangle-quality-poor for direct
  tet meshing.** Decimate + let gmsh remesh, or re-voxelize coarse and build
  hex. Decimation makes degenerate triangles → NaNs (see §6); clean with
  `m.update_faces(m.nondegenerate_faces())`.
- **`ccx` is the CLI solver; `cgx` (GraphiX) is a SEPARATE GUI needing
  XQuartz.** Never depend on cgx in a headless/CI run — parse `.dat`
  (whitespace-tabular, easy) or `.frd` (field, for viz) and visualize in
  rerun.
- **Install paths drift in version.** FreeCAD-bundled `ccx` = 2.23,
  conda-forge = 2.23, the costerwi Homebrew tap ~2.22. Pin conda-forge
  osx-arm64 for reproducible CI; don't assume all paths agree. Upstream has no
  official macOS binary and a bus factor of 1 (Dhondt) — but you hold the GPL
  source and `.inp`/`.frd` are stable Abaqus-compatible formats, so no
  lock-in. (Sourced FEA-solver sweep, 2026-06-13: `ccx` is the robust pick
  across weightings; Code_Aster / Elmer are escalation-only and macOS-painful.)
- **Shell stress in the `.dat` is at the through-thickness GAUSS point, not the
  surface.** CalculiX expands a shell (S8R) to a solid and prints `*EL PRINT,S`
  at ±t/(2·√3); the surface fibre stress = IP stress × √3. Forget it and you
  under-read bending by 1 − 1/√3 = 42% — a passed-but-wrong trap (raw 474 MPa
  vs true 821 MPa on a hull-skin bay). And shell `.dat` stress rows TRAIL a
  `_shell_<id>` label, so `[float(x) for x in line.split()]` throws and
  silently drops EVERY stress row — parse the LEADING numeric tokens only.
  (Both caught live, 2026-06-13, validating a hull panel against an analytic
  von-Kármán-slam anchor.)

---

## 8. Project lessons (append project-specific entries below)

> When this file is copied into a new project, rename this section to the
> project name and log its own hard-won lessons here. Keep the sections
> above as the shared baseline. Newest entries first; date every entry.

<!-- e.g.
### 2026-06-13 — <project>: <one-line symptom>
What looked fine, what was actually wrong, the fix, and the regression
guard you added (which audit/check now catches it).
-->
