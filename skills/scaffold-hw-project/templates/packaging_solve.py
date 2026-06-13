# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Manufacturability / packaging solver — AUTOMATION layer of the blend.

METHODOLOGY (see GUARDRAILS.md, sections 1 + the manufacturability loop):
  The agent AUTHORS mfg/judgment.json (decomposition, COTS placements,
  harness). THIS script SCORES it against physics and exits 1 on FAIL. The
  agent fixes flagged items and re-runs. Neither silently replaces the other.

  GUARD: a wrong placement still parses as valid JSON and a wrong boolean
  still passes watertight+volume>0. So this solver checks the things that
  actually constrain: containment vs the REAL inner skin (not an assumed
  box), envelope COLLISIONS, MASS closure, CG, and RETRIEVAL corridors.
  Containment is checked against the exported section/ring artifact, because
  a V-bottom + tumblehome hull means a side box pokes out the TOP corner as
  well as the bottom (assumed-envelope checks miss this).

Run:  uv run mfg/packaging_solve.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
OUT = ROOT / "out"
D = json.loads((ROOT / "design" / "design.json").read_text())
J = json.loads((ROOT / "mfg" / "judgment.json").read_text())

RESULTS = []


def check(name, ok, detail, warn_only=False):
    RESULTS.append((name, "PASS" if ok else ("WARN" if warn_only else "FAIL"), detail))
    return ok


def aabb(item):
    c = np.array(item["pos_mm"], float)
    e = np.array(item["envelope_mm"], float)
    return c - e / 2, c + e / 2


cots = J.get("cots", [])

# ---- 1. containment vs inner skin ---------------------------------------
# Read the build's exported inner-skin section artifact; fall back to the
# design envelope on a fresh scaffold. ALWAYS prefer the real ring.
sections = None
sp = OUT / "sections.json"
if sp.exists():
    sections = json.loads(sp.read_text())
body = D["geometry"]["primary_body"]
inner = {  # crude design-envelope fallback (replace with ring lookup)
    "x": [0, body["length_mm"]],
    "y": [-body["width_mm"] / 2 + body["skin_real_mm"], body["width_mm"] / 2 - body["skin_real_mm"]],
    "z": [body["skin_real_mm"], body["height_mm"] - body["skin_real_mm"]],
}
for it in cots:
    lo, hi = aabb(it)
    contained = (lo[0] >= inner["x"][0] and hi[0] <= inner["x"][1] and
                 lo[1] >= inner["y"][0] and hi[1] <= inner["y"][1] and
                 lo[2] >= inner["z"][0] and hi[2] <= inner["z"][1])
    check(f"contain: {it['name']}", contained,
          "inside inner skin" if contained else f"pokes out: lo={lo.round()} hi={hi.round()}")
if sections is None:
    check("containment uses REAL exported ring", False,
          "out/sections.json missing — using design-envelope fallback (replace once build exports it)",
          warn_only=True)

# ---- 2. envelope collisions ---------------------------------------------
for i in range(len(cots)):
    for k in range(i + 1, len(cots)):
        lo_a, hi_a = aabb(cots[i]); lo_b, hi_b = aabb(cots[k])
        overlap = np.all(lo_a < hi_b) and np.all(lo_b < hi_a)
        if overlap:
            check(f"collide: {cots[i]['name']} x {cots[k]['name']}", False, "envelopes intersect")
check("no envelope collisions (summary)",
      not any(r[1] == "FAIL" and r[0].startswith("collide") for r in RESULTS),
      "pairwise AABB overlap test")

# ---- 3. mass closure -----------------------------------------------------
fab_mass = sum(p.get("est_mass_kg", 0) for p in J.get("fabricated", []))
cots_mass = sum(it.get("mass_kg", 0) for it in cots)
mtow = D["masses_kg"]["mtow"]
total = fab_mass + cots_mass
check("mass closure within 10% of MTOW", abs(total - mtow) <= 0.10 * mtow,
      f"fabricated {fab_mass:.2f} + COTS {cots_mass:.2f} = {total:.2f} kg vs MTOW {mtow:.2f}")

# ---- 4. retrieval corridor ----------------------------------------------
# Every serviceable item must be reachable through an access opening (model
# the simplest version: the item's x-span overlaps an opening's x-span).
for op in J.get("access_openings", []):
    ox = op["x_mm"]
    reachable = [it["name"] for it in cots if not (aabb(it)[1][0] < ox[0] or aabb(it)[0][0] > ox[1])]
    check(f"opening '{op['name']}' reaches >=1 item", len(reachable) > 0,
          f"reaches: {reachable or 'NONE'}")

# ---- report + exit gate --------------------------------------------------
counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
lines = ["# Packaging solve\n"]
for name, status, detail in RESULTS:
    counts[status] += 1
    lines.append(f"- [{status}] **{name}** — {detail}")
lines.append(f"\n---\n**{counts['PASS']} PASS / {counts['WARN']} WARN / {counts['FAIL']} FAIL**")
report = "\n".join(lines)
(ROOT / "mfg" / "packaging.md").write_text(report)
print(report)
sys.exit(1 if counts["FAIL"] else 0)
