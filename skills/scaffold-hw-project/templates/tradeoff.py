# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "rerun-sdk"]
# ///
"""Scored tradeoff study — resolve a design fork with numbers, not gut.

METHODOLOGY (see GUARDRAILS.md, section 4):
  - Evaluate candidates at the CHEAPEST FIDELITY THAT DISCRIMINATES
    (placement / box layouts over exported sections — NOT a full build each).
  - Score on COMPUTED physics where possible.
  - Run a SENSITIVITY sweep across weight schemes and pick the ROBUST option,
    not the winner of one weighting.
  - Keep candidates SIDE BY SIDE: one rerun Spatial3DView PER candidate,
    tiled in a grid (this template authors that blueprint). Do NOT overwrite
    one recording per candidate.
  - Only the WINNER earns a full build + sim verification.

THE #1 STUDY KILLER (np.interp):
  np.interp REQUIRES ascending xp. For a "lower is better" metric use
  ascending xp with REVERSED fp:  score(x, lo, hi, lower_is_better=True).
  A descending xp does not raise — it SILENTLY INVERTS the metric.

Run:   uv run tradeoff.py
View:  uv run --with rerun-sdk python -m rerun out/tradeoff.rrd
"""
import json
from pathlib import Path

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
D = json.loads((ROOT / "design" / "design.json").read_text())


def score(value, lo, hi, lower_is_better=False):
    """Map a physical value to a 2..5 score. Clamps to the [lo,hi] band.
    GUARDRAIL: np.interp needs ascending xp; for lower-is-better we keep xp
    ascending and REVERSE the fp so we never silently invert."""
    fp = [5.0, 2.0] if lower_is_better else [2.0, 5.0]
    return float(np.interp(value, [lo, hi], fp))


# ---- 1. Candidates -------------------------------------------------------
# Define each design fork option at the placement level. Replace the toy
# fields with the real placement parameters of YOUR fork (e.g. battery box
# centroid, sponson station, strut angle). Compute physics from these.
CANDIDATES = {
    "baseline":   {"cg_x_mm": 500, "pitch_inertia": 1.0, "pack_density_kgL": 1.50, "access": 5},
    "low_keel":   {"cg_x_mm": 505, "pitch_inertia": 0.8, "pack_density_kgL": 1.55, "access": 3},
    "outboard":   {"cg_x_mm": 498, "pitch_inertia": 1.3, "pack_density_kgL": 1.40, "access": 4},
}

# ---- 2. Metrics (computed, scored, direction-aware) ----------------------
# (band_lo, band_hi, lower_is_better). Pick bands from the design envelope.
METRICS = {
    "pitch_inertia":    (0.8, 1.3, True),    # crisp rotation: lower better
    "pack_density_kgL": (1.0, 1.6, False),   # denser pack within cap: higher better
    "access":           (1, 5, False),       # serviceability judgment: higher better
}


def scored(cand):
    return {m: score(cand[m], lo, hi, lib) for m, (lo, hi, lib) in METRICS.items()}


SCORES = {name: scored(c) for name, c in CANDIDATES.items()}

# ---- 3. Sensitivity across weight schemes (pick the ROBUST winner) -------
SCHEMES = {
    "equal":        {m: 1.0 for m in METRICS},
    "performance":  {"pitch_inertia": 3, "pack_density_kgL": 1, "access": 1},
    "serviceable":  {"pitch_inertia": 1, "pack_density_kgL": 1, "access": 3},
}


def weighted(name, w):
    s = SCORES[name]
    return sum(s[m] * w[m] for m in METRICS) / sum(w.values())


sensitivity = {sch: {n: weighted(n, w) for n in CANDIDATES} for sch, w in SCHEMES.items()}
wins = {n: sum(max(sensitivity[s], key=sensitivity[s].get) == n for s in SCHEMES)
        for n in CANDIDATES}
robust_winner = max(wins, key=wins.get)

# ---- 4. Markdown report --------------------------------------------------
lines = ["# Tradeoff study\n", "## Per-candidate scores\n",
         "| candidate | " + " | ".join(METRICS) + " |",
         "|" + "---|" * (len(METRICS) + 1)]
for n in CANDIDATES:
    lines.append(f"| {n} | " + " | ".join(f"{SCORES[n][m]:.2f}" for m in METRICS) + " |")
lines += ["\n## Sensitivity (weighted total, per scheme)\n",
          "| scheme | " + " | ".join(CANDIDATES) + " |",
          "|" + "---|" * (len(CANDIDATES) + 1)]
for sch in SCHEMES:
    lines.append(f"| {sch} | " + " | ".join(f"{sensitivity[sch][n]:.2f}" for n in CANDIDATES) + " |")
lines += [f"\n**Schemes won:** " + ", ".join(f"{n}={wins[n]}" for n in CANDIDATES),
          f"\n**Robust winner: {robust_winner}** "
          f"(wins {wins[robust_winner]}/{len(SCHEMES)} weight schemes — "
          f"pick this, then give ONLY it a full build + sim verification)."]
(OUT / "tradeoff.md").write_text("\n".join(lines))
print("\n".join(lines))

# ---- 5. Side-by-side rerun: one Spatial3DView PER candidate, tiled -------
rr.init("project_tradeoff", spawn=False)
rr.save(OUT / "tradeoff.rrd")
for name, c in CANDIDATES.items():
    # Draw each candidate as outlined placement boxes under its own path.
    # (Use the REAL exported section/ring as shared context in a real study.)
    rr.log(f"cand/{name}/box", rr.Boxes3D(
        centers=[[c["cg_x_mm"], 0, 75]], sizes=[[300, 150, 120]],
        labels=[f"{name}  robust={'YES' if name==robust_winner else 'no'}"]),
        static=True)
rr.send_blueprint(rrb.Blueprint(rrb.Grid(
    contents=[rrb.Spatial3DView(origin=f"/cand/{n}", name=n) for n in CANDIDATES])))
print(f"\nview tiled: uv run --with rerun-sdk python -m rerun {OUT / 'tradeoff.rrd'}")
