---
name: run-tradeoff-study
description: >-
  Resolve a hardware design fork with a scored tradeoff study instead of a
  gut call. Use when a real design decision branches (layout, structure,
  battery placement, sponsons, strut geometry, ...). Drives a
  placement-level study scored on computed physics, a sensitivity sweep
  across weight schemes to pick the ROBUST option, and a tiled side-by-side
  rerun comparison (one Spatial3DView per candidate). Only the winner earns
  a full build + sim.
---

# Run a scored tradeoff study

Gut picks lose. A scored study with sensitivity earns its keep — it has
overturned the "obvious" choice repeatedly. This skill runs one correctly.

## The method (four rules)

1. **Cheapest fidelity that discriminates.** Evaluate candidates at the
   PLACEMENT level — box layouts over the exported sections/rings — NOT a
   full build per candidate. Build only the winner.
2. **Score on COMPUTED physics.** CG, inertia, margin, density, containment,
   clearance — computed from the candidate parameters, not asserted.
3. **Sensitivity, then ROBUST winner.** Sweep several weight schemes
   (equal / performance-leaning / serviceability-leaning / ...). Pick the
   candidate that wins the MOST schemes, not the one that wins a single
   weighting. A lone-weighting winner hides ties and fragile leads.
4. **Side by side.** One rerun `Spatial3DView` PER candidate, tiled in a
   grid (a `rrb.Grid` of views). Never overwrite one recording per
   candidate — the whole point is to see them together.

## The gotchas (each cost a wrong answer once — see GUARDRAILS.md §4)

- **`np.interp` requires ASCENDING `xp`.** For "lower is better" use
  ascending `xp` with REVERSED `fp` (`np.interp(x, [lo, hi], [5, 2])`). A
  descending `xp` does not raise — it SILENTLY INVERTS the metric and makes
  the worst candidate look best.
- **Score what actually constrains, not a proxy that looks placed.** E.g.
  pack DENSITY (kg/L) catches a box too small to hold its cells; a "placed"
  box can still be infeasible.
- **Containment vs the REAL ring, not an assumed beam.** A V-bottom +
  tumblehome hull means a side box pokes out the TOP corner as well as the
  bottom. Check against the exported section, not an envelope you imagined.
- **Drop metrics that don't discriminate.** If a metric is ~constant across
  candidates (e.g. CG_x when payload sits at the CG), it earns no column —
  find one that separates them.

## Procedure

1. If the project already has `tradeoff.py` (from `scaffold-hw-project`),
   start there. Otherwise copy the template:
   `cp "${CLAUDE_PLUGIN_ROOT}/skills/scaffold-hw-project/templates/tradeoff.py" ./tradeoff.py`

2. Define the CANDIDATES dict: each option as its placement parameters
   (centroid, station, angle, envelope). Read shared context (the hull
   ring, the deck) from the build's exported `out/*.json`.

3. Define METRICS as `(band_lo, band_hi, lower_is_better)` and COMPUTE each
   candidate's physical value. Use the `score()` helper (it handles the
   `np.interp` direction safely).

4. Define SCHEMES (weight vectors). Compute the weighted total per
   candidate per scheme, count scheme-wins, and report the robust winner.

5. Run `uv run tradeoff.py`. Read `out/tradeoff.md`; open the tiled
   recording: `uv run --with rerun-sdk python -m rerun out/tradeoff.rrd`.

6. Record the DECISION and its rationale (which schemes the winner won, and
   the durable lessons that survive the specific numbers) in the project's
   AGENTS.md or a `tradeoff_<fork>.md`. Then — and only then — give the
   winner a full build + sim verification.

7. If the study surprised you (a silent inversion, a non-discriminating
   metric), append the lesson to `GUARDRAILS.md`.
