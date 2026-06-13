---
name: guardrails-check
description: >-
  Run the silent-failure guardrails checklist before trusting a sim, audit,
  build, or tradeoff result in a hardware-as-code project — and record new
  lessons when something silently gives a wrong answer. Use when a number
  surprises you, before declaring a result correct, or when reviewing a
  geometry/sim/audit change. This is the living-checklist entry point: it
  both APPLIES the gotchas and APPENDS new ones.
---

# Guardrails check (and how to grow the checklist)

The meta-rule: **a result that "ran clean" is not a result that is
correct.** Voxel kernels, CFD configs, and `np.interp` fail SILENTLY — no
exception to catch — which is the worst failure mode for an agent. Every
derived number must agree with an independent anchor before you trust it.

The full, living checklist is `${CLAUDE_PLUGIN_ROOT}/GUARDRAILS.md` (and the
project-local copy at `<project>/GUARDRAILS.md` after scaffolding). Read it.
This skill is the workflow for using it and keeping it current.

## Before declaring ANY result correct, sweep these

- **Wrong boolean, clean mesh.** A failed subtract / flood-filled cavity /
  no-op union still yields a watertight, positive-volume mesh. Did an audit
  assert the EXPECTED bbox/volume/CG, not just ">0"?
- **`np.interp` direction.** Any value→score map: is `xp` ascending? Is
  lower-is-better done with ascending `xp` + REVERSED `fp`? Hand-check a
  value at each end of the band.
- **Anchor cross-check.** Is every derived number checked against a `[PUB]`
  value, an analytic formula, or the REAL exported artifact — not an assumed
  envelope?
- **Voxel/CAD silence.** Union first, subtract last, vent every cavity? No
  voxel artifact on the outer mold line (sub-voxel wall reads as closed)?
  Loft `ruled=` pinned?
- **CFD config.** `FLUID_MODEL` set explicitly (ideal-gas trap)? Validated
  against an analytic anchor and a grid-convergence study?
- **Sim signs + indices.** Every control-derivative sign written down and
  self-checked at runtime? State-vector slices named (the v-vs-w trap)?
  Subsystems calibrated open-loop before closing the loop?
- **rerun.** `rr.save()` before opening the viewer (it REPLACES the sink)?
  `vertex_normals` on every `Mesh3D`? Milestone archived to
  `out/history/<date>/` before regenerating?
- **Mesh hygiene.** Decimated before queries? Degenerate faces cleaned
  (`update_faces(nondegenerate_faces())`, `np.nanmax`)?
- **Look at it.** Did you open the render — including the underside and the
  region you touched?

## When something silently gave a wrong answer: append the lesson

This is how the artifact stays LIVING. Open the project's `GUARDRAILS.md`
(or the plugin's, for a cross-project lesson) and append to the right
section — section 7 for project-specific, sections 1-6 for a reusable
class. NEWEST FIRST, dated, with three things:

1. **Symptom** — what looked fine but was wrong.
2. **Cause + fix** — the silent failure and how you corrected it.
3. **Regression guard** — which audit/check now catches it, so it cannot
   silently recur. (If there isn't one, add it via `add-scored-audit`.)

```
### 2026-06-13 — <project>: side battery box scored best on takeoff (wrong)
Symptom: the worst layout won the takeoff metric in the tradeoff.
Cause: np.interp called with a DESCENDING xp on a lower-is-better metric,
which silently inverted it. Fix: ascending xp + reversed fp via score().
Guard: tradeoff.py now hand-checks score() at both band ends in a smoke test.
```

A lesson without a regression guard will be re-learned. Always close the
loop with a check that makes the silent failure loud next time.
