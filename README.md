# Agentic Digital Twins, as Code

A Claude Code plugin for building **engineering digital twins as code with AI
agents** — code-defined geometry + **digital twin simulation** (physics, CFD,
FEA) + scored verification, with **rerun** for visualization and data fusion
toward live, closed-loop twins. It packages the conventions and hard-won
gotchas from a working modeling-and-simulation monorepo (lunar lander,
aircraft, a real-aircraft digital twin), so a new hardware / CAD / sim project
starts at best-practice on day one and the lessons keep accruing as you learn.
**Hardware-in-the-loop ready.**

It is a **living artifact**: the guardrails checklist and project AGENTS.md
are structured for new lessons, gotchas, and skills to append cleanly.

## What "digital twins as code" means here

- **Spec/geometry is code.** One source-of-truth `design.json`, mirrored
  into the build source (e.g. `Design.cs`). Published/measured values tagged
  `[PUB]`; everything else derived and traceable.
- **Every requirement gets an executable, scored audit.** PASS/WARN/FAIL,
  exit 1 on FAIL, a markdown report. Audits read the build's exported JSON
  artifacts — they never duplicate a geometry constant.
- **uv single-file PEP 723 scripts** (`uv run script.py`), not venvs.
  numpy / scipy / trimesh are the workhorses.
- **Visualization is rerun** — one `.rrd` per concern, milestones archived,
  every mesh gets `vertex_normals`.
- **A verification ladder** for assemblies (components → intersections →
  contact graph → single-island check) with joints modeled as components.
- **FEA is tiered** — analytic audit checks → in-house numpy beam FEA →
  gmsh + CalculiX (`ccx`) for continuum parts, each tier validated against
  the one below (a `*BUCKLE` eigenvalue must match the analytic Euler `P_cr`).
- **Design iteration is a scored tradeoff study with sensitivity** — pick
  the robust option, not the one-weighting winner; only the winner gets a
  full build.
- **Manufacturability is an automation⇄agent blend** — the agent authors
  judgment, automation scores it, loop until it packs.
- **Guardrails are gold.** Silent-failure traps (a wrong boolean still
  passes watertight; `np.interp` needs ascending `xp`; voxel kernels fail
  silently; CFD `FLUID_MODEL` defaults) live in an append-only checklist.

## What's in the plugin

```
agentic-digital-twin/
├── .claude-plugin/
│   ├── plugin.json            # manifest (name, version, description, author, keywords)
│   └── marketplace.json       # single-plugin marketplace catalog (for distribution)
├── GUARDRAILS.md              # the LIVING gotcha checklist — append new lessons here
├── README.md
├── agents/
│   └── hardware-as-code-engineer.md   # the methodology subagent persona
└── skills/
    ├── scaffold-hw-project/   # stand up a new project at best-practice
    │   ├── SKILL.md
    │   └── templates/         # runnable skeletons copied into the new project:
    │       ├── design.json            #   source-of-truth design of record
    │       ├── Design.cs              #   build-source mirror stub
    │       ├── audit.py               #   scored audit harness
    │       ├── viz.py                 #   rerun visualization harness
    │       ├── tradeoff.py            #   scored study + sensitivity + tiled compare
    │       ├── fea_continuum.py       #   tier-3 continuum FEA (gmsh + CalculiX), anchor-gated
    │       ├── judgment.json          #   manufacturability AGENT layer
    │       ├── packaging_solve.py     #   manufacturability AUTOMATION layer
    │       └── AGENTS.md              #   repository map + workflow + guardrails
    ├── add-scored-audit/      # add one PASS/WARN/FAIL check the right way
    ├── run-tradeoff-study/    # placement-level study + sensitivity + side-by-side
    ├── continuum-fea/         # tier-3 stress/buckling: gmsh + CalculiX, validated vs analytic
    ├── manufacturability-loop/# the automation⇄agent packaging loop
    └── guardrails-check/      # apply the checklist + append new lessons
```

### Skills

| Skill | What it does |
| :-- | :-- |
| `scaffold-hw-project` | Creates a new project with the design-of-record, a scored-audit harness, a rerun viz harness, a tradeoff-study template, the manufacturability judgment+solver pair, and an AGENTS.md + GUARDRAILS.md — all runnable skeletons, not prose. |
| `add-scored-audit` | Adds a single executable requirement check (reads exported JSON, asserts an expected value, exits 1 on FAIL) and rejects the anti-patterns (duplicated constants, `>0` instead of expected, WARN hiding a FAIL). |
| `run-tradeoff-study` | Resolves a design fork with a placement-level scored study, a sensitivity sweep across weight schemes, and a tiled side-by-side rerun comparison; only the robust winner earns a full build. |
| `continuum-fea` | Runs the tier-3 continuum FEA (brackets, panels, shells, lugs) with gmsh + CalculiX (`ccx`): tet-mesh → Abaqus `.inp` → solve headless → parse → VALIDATE against the analytic tier (`*BUCKLE` `P_cr` / cantilever deflection) → mesh convergence → stress field to rerun. Refuses to trust a single mesh. |
| `manufacturability-loop` | Drives the agent-authors-judgment / automation-scores-it packaging loop (containment, collisions, mass closure, CG, retrieval) until it packs. |
| `guardrails-check` | Sweeps the silent-failure checklist before you trust a result, and is the entry point for appending a new lesson with its regression guard. |

### Agent

`hardware-as-code-engineer` — a subagent persona embodying the whole
methodology and the guardrails, which distrusts any number not cross-checked
against an anchor. Appears as `agentic-digital-twin:hardware-as-code-engineer`.

## Install

This plugin is its own repo (`JMMonte/agentic-digital-twin`). Its
`.claude-plugin/` directory holds BOTH a `plugin.json` (so the directory is
a valid plugin) and a `marketplace.json` (so the same directory doubles as a
single-plugin marketplace via `"source": "./"`).

### Option A — from GitHub (recommended)

```bash
/plugin marketplace add JMMonte/agentic-digital-twin
/plugin install agentic-digital-twin@agentic-digital-twin-marketplace
```

### Option B — from a local clone

```bash
git clone https://github.com/JMMonte/agentic-digital-twin
/plugin marketplace add ./agentic-digital-twin        # the dir doubles as the marketplace root
/plugin install agentic-digital-twin@agentic-digital-twin-marketplace
# or, for one session without installing:
claude --plugin-dir ./agentic-digital-twin
```

Validate at any time:

```bash
claude plugin validate ./agentic-digital-twin --strict
```

## Use

```
/agentic-digital-twin:scaffold-hw-project     # start a new project
/agentic-digital-twin:add-scored-audit        # add a requirement check
/agentic-digital-twin:run-tradeoff-study      # resolve a design fork
/agentic-digital-twin:continuum-fea           # tier-3 stress/buckling (gmsh + CalculiX)
/agentic-digital-twin:manufacturability-loop  # pack the internals
/agentic-digital-twin:guardrails-check        # sweep the gotchas / log a lesson
```

Or just ask, and Claude invokes the right skill / the
`hardware-as-code-engineer` agent based on the task.

## How to EXTEND it (this is the point — it's a living artifact)

1. **A new gotcha / lesson** → append to `GUARDRAILS.md`. Newest first,
   dated, with symptom + cause/fix + the regression guard you added. Reusable
   classes go in sections 1-6; project-specific in section 7. The
   `guardrails-check` skill walks you through it. The scaffolder copies this
   file into every new project, so improvements propagate to new projects
   and each project also grows its own local lessons.

2. **A new skill** → add `skills/<name>/SKILL.md` with YAML frontmatter
   (`name` + a trigger-rich `description`). It is auto-discovered; bump
   `version` in `plugin.json` so installed users get it.

3. **A new template** → drop it in
   `skills/scaffold-hw-project/templates/` and add a `cp` line to that
   skill's procedure so new projects pick it up.

4. **Refine the agent persona** → edit
   `agents/hardware-as-code-engineer.md`.

5. **Release** → bump `version` in BOTH `plugin.json` and the
   `marketplace.json` entry (plugin.json wins if they differ), and note the
   change. Without a version bump, installed users keep the cached copy.

## Spec sources

Built against the current Claude Code plugin spec:

- [Plugins reference](https://code.claude.com/docs/en/plugins-reference) —
  manifest schema, component layout, `${CLAUDE_PLUGIN_ROOT}`, validation.
- [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
  — `marketplace.json` schema, `source`, `strict`.
- [Official plugin directory](https://github.com/anthropics/claude-plugins-official).

Methodology source: the `AGENTS.md` files of the `lander/`, `aircraft/`, and
`seagull/` projects in this monorepo.
