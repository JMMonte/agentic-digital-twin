---
name: scaffold-hw-project
description: >-
  Scaffold a new simulation-in-the-loop, hardware-as-code project at
  best-practice on day one. Use when starting a new hardware/CAD/sim model,
  a digital twin, or any project where geometry is code and requirements
  must be verified by executable audits. Creates the design-of-record
  (design.json) + a build-source mirror stub, a scored-audit harness, a
  rerun viz harness, a tradeoff-study template, a manufacturability
  judgment+solver pair, an AGENTS.md with the repository-map convention and
  the guardrails checklist, and a project-local GUARDRAILS.md.
---

# Scaffold a hardware-as-code project

This skill stands up the full methodology skeleton in a new (or existing)
project directory. Everything it writes is a runnable, opinionated starting
point drawn from a working monorepo — not vague prose. The user fills in
the geometry; the harness and the conventions are already correct.

## What you produce

```
<project>/
├── AGENTS.md              # repository map + workflow + guardrails (CLAUDE.md symlinks to it)
├── GUARDRAILS.md          # the living gotcha checklist (project-local copy)
├── design/
│   ├── design.json        # SINGLE SOURCE OF TRUTH (anchors [PUB] + derived)
│   ├── materials.json     # cited material-property source of truth (NEVER hallucinate)
│   └── Design.cs          # build-source MIRROR stub (or Design.py — match the kernel)
├── audit.py               # scored audit harness (PASS/WARN/FAIL, exit 1 on FAIL)
├── viz.py                 # rerun visualization harness
├── tradeoff.py            # placement-level scored tradeoff study + sensitivity
├── fea_continuum.py       # tier-3 continuum FEA (gmsh + CalculiX), validated vs the analytic tier
├── import_cad.py          # bring-your-own-CAD: import STEP/STL -> out/imported.json for the audits
├── mfg/
│   ├── judgment.json      # AGENT layer: decomposition, COTS placements, harness
│   └── packaging_solve.py # AUTOMATION layer: scores the judgment, exit 1 on FAIL
└── out/                   # build/viz/sim artifacts (gitignored; history/ for milestones)
```

## Procedure

1. **Confirm the target.** Ask the user for the project directory name and
   the geometry kernel they will use (PicoGK/C#, build123d/Python, OpenSCAD,
   CadQuery, …). The build-source mirror is named to match
   (`Design.cs` for C#, `design_mirror.py` for Python). Default to the
   project root the user is in if they don't specify.

2. **Copy the templates.** The template files live next to this skill at
   `${CLAUDE_PLUGIN_ROOT}/skills/scaffold-hw-project/templates/`. Copy each
   to its destination and rename `AGENTS.md` ↔ `CLAUDE.md` (symlink
   `CLAUDE.md -> AGENTS.md` so both AI harnesses read the same canonical
   file). Copy the plugin's top-level `GUARDRAILS.md`
   (`${CLAUDE_PLUGIN_ROOT}/GUARDRAILS.md`) into the project so its own
   lessons accrue beside its code.

   ```bash
   PROJ="<project-dir>"          # e.g. ./rover
   TPL="${CLAUDE_PLUGIN_ROOT}/skills/scaffold-hw-project/templates"
   mkdir -p "$PROJ/design" "$PROJ/mfg" "$PROJ/out/history"
   cp "$TPL/design.json"          "$PROJ/design/design.json"
   cp "$TPL/materials.json"       "$PROJ/design/materials.json"   # cited material props; never hallucinate
   cp "$TPL/Design.cs"            "$PROJ/design/Design.cs"     # rename if Python kernel
   cp "$TPL/audit.py"             "$PROJ/audit.py"
   cp "$TPL/viz.py"               "$PROJ/viz.py"
   cp "$TPL/tradeoff.py"          "$PROJ/tradeoff.py"
   cp "$TPL/fea_continuum.py"     "$PROJ/fea_continuum.py"   # tier-3 gmsh+CalculiX, runs once ccx is installed
   cp "$TPL/import_cad.py"        "$PROJ/import_cad.py"      # bring-your-own-CAD entry point (STEP/STL -> artifacts)
   cp "$TPL/judgment.json"        "$PROJ/mfg/judgment.json"
   cp "$TPL/packaging_solve.py"   "$PROJ/mfg/packaging_solve.py"
   cp "$TPL/AGENTS.md"            "$PROJ/AGENTS.md"
   cp "${CLAUDE_PLUGIN_ROOT}/GUARDRAILS.md" "$PROJ/GUARDRAILS.md"
   ( cd "$PROJ" && ln -sf AGENTS.md CLAUDE.md )
   printf 'out/\n' > "$PROJ/.gitignore"
   ```

3. **Tailor the design of record.** Edit `design/design.json` WITH the user:
   set the project name, the coordinate system, the published anchors
   (tag each `[PUB]`), and the first derived geometry. Every non-published
   number must trace to an anchor or a sizing script. Then stub the matching
   constants in the build-source mirror — JSON first, mirror second.

4. **Wire the audit to real artifacts.** `audit.py` ships reading
   `design/design.json` plus placeholder `out/*.json`. Point its checks at
   the artifacts the build will actually export, and replace the example
   checks with the project's real requirements. Keep the rule: audits read
   exported JSON, they never duplicate a geometry constant.

5. **Fill in AGENTS.md.** The template has the repository-map convention,
   the build+verify loop, and the guardrails checklist pre-written. Replace
   the bracketed placeholders with project specifics (kernel, units, the
   actual harness list). This file plus GUARDRAILS.md is where every future
   lesson lands.

6. **Verify the skeleton runs.** `uv run audit.py` should execute and print
   a scored report (it will FAIL until the build exports real artifacts —
   that's correct; a fresh project has unmet requirements). `uv run viz.py`
   and `uv run tradeoff.py` should run on the placeholder data. `uv run
   fea_continuum.py` validates the tier-3 gmsh+CalculiX pipeline against a
   closed-form cantilever and PASSes once `ccx` is installed (FreeCAD bundles
   it; else `conda install -c conda-forge calculix`) — it is the template for
   the project's real continuum parts. See the `continuum-fea` skill.

## Conventions baked into the templates (do not undo)

- design.json is the source of truth; the build source mirrors it.
- Audits are scored, exit 1 on FAIL, write a markdown report, and read
  exported JSON (never hard-code geometry).
- uv single-file scripts with PEP 723 headers.
- rerun for viz: one `.rrd` per concern, `vertex_normals` on every mesh,
  archive milestones to `out/history/<date>/`.
- Tradeoff studies score at the cheapest discriminating fidelity, include a
  sensitivity sweep, and pick the robust option.
- Manufacturability is judgment (agent) scored by automation.

After scaffolding, suggest the `add-scored-audit`, `run-tradeoff-study`,
and `guardrails-check` skills for the next steps, and the
`hardware-as-code-engineer` agent for the build.
