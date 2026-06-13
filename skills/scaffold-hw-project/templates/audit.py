# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Scored audit harness — the executable record of "every requirement passes".

METHODOLOGY:
  - Reads ONLY design/design.json + the build's exported out/*.json artifacts.
    NO geometry constant is duplicated here (regex from source or read JSON).
  - Each requirement is one check() -> PASS / WARN / FAIL.
  - WARN is for HONEST, documented shortfalls (physics vs marketing), never
    for hiding a real failure.
  - Writes out/audit_report.md and EXITS 1 on any FAIL (CI gate).

  THE GOLD RULE (see GUARDRAILS.md): a wrong boolean still passes
  watertight + volume>0. So checks assert EXPECTED bbox / volume / CG against
  a known value, not just ">0". Cross-check derived numbers against an
  anchor (published spec, analytic formula, or the REAL exported artifact).

Run after every geometry/design change:  uv run audit.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
OUT = ROOT / "out"
D = json.loads((ROOT / "design" / "design.json").read_text())


def load(name: str, default=None):
    """Read a build-exported artifact; tolerate absence on a fresh project."""
    p = OUT / name
    if p.exists():
        return json.loads(p.read_text())
    return default


# Build exports (point these at the real artifacts your build writes):
COMP = load("components.json", default={})       # {name: {bboxMin, bboxMax, volume_cm3, cg_mm}}
CONTACTS = load("contacts.json", default=[])     # [{a, b, overlap_cm3}, ...]

RESULTS = []  # (section, name, status, detail)


def check(section, name, ok, detail, warn_only=False):
    """PASS if ok; else WARN (documented shortfall) or FAIL (hard gate)."""
    status = "PASS" if ok else ("WARN" if warn_only else "FAIL")
    RESULTS.append((section, name, status, detail))
    return ok


def expect(section, name, value, target, tol, units="", warn_only=False):
    """Assert a derived/built value is near a known anchor (the GOLD rule).
    NEVER assert merely ">0"; assert it matches what you expect."""
    ok = abs(value - target) <= tol
    return check(section, name, ok,
                 f"{value:.3g}{units} vs expected {target:.3g}{units} (+-{tol:g})",
                 warn_only=warn_only)


# =================================================== 1 published anchors ===
sec = "1 published anchors"
anchors = D.get("anchors_published", {})
# Cross-check every [PUB] anchor against the as-built geometry. Example:
if COMP and "primary_body" in COMP:
    built_len = COMP["primary_body"]["bboxMax"][0] - COMP["primary_body"]["bboxMin"][0]
    expect(sec, "body length matches design", built_len,
           D["geometry"]["primary_body"]["length_mm"], tol=2 * D["coordinate_system"]["voxel_mm"],
           units=" mm")
else:
    check(sec, "build artifacts present", False,
          "out/components.json not found — run the build first (expected on a fresh scaffold)")

# =================================================== 2 mass / CG closure ===
sec = "2 mass / CG closure"
masses = {k: v for k, v in D["masses_kg"].items() if isinstance(v, dict) and "mass" in v}
total = sum(m["mass"] for m in masses.values())
mtow = D["masses_kg"]["mtow"]
expect(sec, "mass sums to MTOW", total, mtow, tol=0.05 * mtow, units=" kg")
if masses:
    cg = np.sum([np.array(m["station_mm"]) * m["mass"] for m in masses.values()], axis=0) / total
    check(sec, "CG computed", True, f"CG = [{cg[0]:.0f}, {cg[1]:.0f}, {cg[2]:.0f}] mm")

# =================================================== 3 assembly integrity ==
sec = "3 assembly integrity"
# Single-island union-find over the contact graph (see GUARDRAILS verification
# ladder): atomic components -> pairwise intersections -> contact graph ->
# one connected island. Catches floating parts a volume check cannot.
if COMP:
    names = list(COMP.keys())
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in CONTACTS:
        if c.get("overlap_cm3", 0) > 0 and c["a"] in parent and c["b"] in parent:
            parent[find(c["a"])] = find(c["b"])
    islands = {find(n) for n in names}
    check(sec, "single connected assembly (no floating parts)", len(islands) == 1,
          f"{len(islands)} island(s) over {len(names)} components")
else:
    check(sec, "assembly graph", False, "no components exported yet")

# =================================================== 4 requirements ========
sec = "4 requirements"
# Each design.json requirement gets a scored check. Wire these to real
# measured/exported values; the placeholders below show both directions.
reqs = D.get("requirements", {})
for rname, r in reqs.items():
    if rname.startswith("_"):
        continue
    # Replace `measured` with the real value read from out/*.json.
    measured = r.get("min", r.get("max", 0.0))  # placeholder: self-satisfying
    if "min" in r:
        check(sec, rname, measured >= r["min"], f"measured {measured} >= min {r['min']}")
    elif "max" in r:
        check(sec, rname, measured <= r["max"], f"measured {measured} <= max {r['max']}")

# =================================================== report + exit gate =====
lines = ["# Audit report\n"]
counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
cur = None
for section, name, status, detail in RESULTS:
    if section != cur:
        lines.append(f"\n## {section}\n")
        cur = section
    counts[status] += 1
    icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[status]
    lines.append(f"- [{icon}] **{name}** — {detail}")
lines.append(f"\n---\n**{counts['PASS']} PASS / {counts['WARN']} WARN / {counts['FAIL']} FAIL**")
report = "\n".join(lines)
OUT.mkdir(exist_ok=True)
(OUT / "audit_report.md").write_text(report)
print(report)
sys.exit(1 if counts["FAIL"] else 0)
