# [PROJECT] — agent guide

> AGENTS.md is canonical and vendor-neutral; CLAUDE.md is a symlink to it.
> Whatever AI agent or harness you are, read this file, then GUARDRAILS.md,
> before touching the geometry.

[One-paragraph description: what this is, what it models, and — if it's a
digital twin of a REAL thing — the published anchors it is bound to and the
cardinal rule that everything else is DERIVED and must stay traceable.]

## The cardinal rule

- `design/design.json` is the SINGLE SOURCE OF TRUTH. The build source
  (`design/Design.cs` or `design/design_mirror.py`) MIRRORS it — update the
  JSON FIRST, then the mirror. Published/measured values are tagged `[PUB]`;
  every other number is DERIVED and traces to an anchor or a sizing script.
- Never present a derived number as if it were published.

## Repository map

- **Build ([kernel])**: `[Program.cs / build.py]` + `design/Design.cs`
  mirror. The build EXPORTS every geometry result to `out/*.json`
  (components, contacts, sections, ...) — these JSON artifacts are the
  single source of truth that the audits read. The build NEVER lets an audit
  re-derive geometry.
- **`design/`** — source of truth: `design.json` (+ mirror), sizing scripts.
- **`out/`** — all build/viz/sim artifacts (gitignored). Milestones archived
  to `out/history/<date-rev>/`.
- **Runnable harnesses (`uv run <name>.py`, PEP 723 single-file scripts)**:
  - `audit.py` — scored audit: anchors / geometry / mass-CG / assembly /
    requirements. PASS/WARN/FAIL, exit 1 on FAIL, writes `out/audit_report.md`.
  - `viz.py` — rerun visualization (one `.rrd` per concern).
  - `tradeoff.py` — placement-level scored study + sensitivity sweep.
  - `mfg/packaging_solve.py` — scores `mfg/judgment.json` (containment,
    collisions, mass closure, CG, retrieval). Exit 1 on FAIL.
- **`mfg/`** — manufacturability blend: `judgment.json` (AGENT authors:
  fabricated vs COTS, placements, harness) scored by `packaging_solve.py`
  (AUTOMATION). Loop until it packs.

## Build & verify (the loop)

```sh
[build command]                 # geometry -> out/*.json + meshes
uv run audit.py                 # MUST end 0 FAIL
uv run mfg/packaging_solve.py   # MUST end 0 FAIL
uv run viz.py                   # then open the viewer and LOOK at it
# view: uv run --with rerun-sdk python -m rerun out/model.rrd
```

Every change MUST end with: build green, ALL audits 0 FAIL, AND a render you
actually open — including the underside and any region you touched.

## Design iteration = scored tradeoff study (a PRINCIPLE)

Resolve a design fork (layout, structure, ...) with a SCORED study at the
cheapest fidelity that discriminates (placements over full builds) + a
SENSITIVITY sweep across weight schemes. Pick the ROBUST option, not the
one-weighting winner. Only the winner earns a full build + sim. Keep
candidates SIDE BY SIDE (one rerun Spatial3DView per candidate, tiled).

## Guardrails checklist (the GOLD — read GUARDRAILS.md in full, keep it current)

A result that "ran clean" is not a result that is correct. The traps that
fail SILENTLY (worst case for an agent — no exception to catch):

- A wrong boolean still passes watertight + volume>0 → audits assert
  EXPECTED bbox/volume/CG, never just ">0".
- `np.interp` needs ASCENDING `xp`; lower-is-better = ascending `xp` +
  REVERSED `fp`, else it silently inverts the metric.
- Sanity-check derived metrics against the REAL exported artifact, not an
  assumed envelope.
- Voxel/CAD kernels fail silently: union first, subtract last, vent every
  cavity; keep voxel artifacts off the outer mold line; pin loft `ruled=`.
- CFD `FLUID_MODEL` defaults silently (ideal-gas trap) — set it explicitly
  and validate against an analytic anchor + grid study.
- rerun: `rr.save()` REPLACES the sink; every `Mesh3D` needs
  `vertex_normals`; archive milestones to `out/history/<date>/` before
  regenerating.

> When something silently gives a wrong answer and you find out why, APPEND
> the lesson to `GUARDRAILS.md` (section 7, newest first, dated, with the
> symptom + the fix + the regression guard you added). This file and
> GUARDRAILS.md are the project's living memory.

## Open items / next steps

- [Track design forks still unresolved, known WARNs and why they're honest,
  and the escalation path for higher-fidelity verification.]
