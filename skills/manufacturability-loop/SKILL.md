---
name: manufacturability-loop
description: >-
  Drive the automation-agent manufacturability/packaging loop for a
  hardware-as-code project: an agent authors engineering judgment
  (decomposition into fabricated vs COTS, placements, harness, sourcing) and
  automation scores it (skin containment, envelope collisions, mass closure,
  CG, retrieval corridors), looping until it packs. Use when laying out
  internals, decomposing a design for fabrication, or packaging COTS into an
  envelope.
---

# The manufacturability / packaging loop

Manufacturability is a deliberate BLEND: judgment that only a human-or-agent
can author, scored by automation that a human-or-agent cannot fake.
**Never let one silently replace the other** — a wrong placement still
parses as valid JSON, and a wrong boolean still passes watertight+volume>0.
The solver is what proves the judgment actually fits.

## The two layers

- **AGENT layer — `mfg/judgment.json`** (you author this): how the design
  decomposes into FABRICATED parts vs COTS, the cable/fluid harness, the
  joints, and each item's PLACEMENT (position + envelope) and SOURCING.
- **AUTOMATION layer — `mfg/packaging_solve.py`** (this scores it): skin
  containment against the REAL inner ring, envelope COLLISIONS, MASS
  closure, CG, clearance to moving parts, and RETRIEVAL corridors. Exit 1
  on FAIL.

## The loop

1. **Author judgment.** Edit `mfg/judgment.json`: list fabricated parts
   (process + material + est. mass), COTS (vendor PN + mass + pos +
   envelope + sourcing note), the harness, joints, and access openings. Use
   real datasheet envelopes — a too-small box that "looks placed" fails the
   density check.

2. **Score it.** `uv run mfg/packaging_solve.py`. Read `mfg/packaging.md`.

3. **Fix what's flagged.** Each FAIL names the item and the violation:
   - *containment* → the item pokes out the skin; move it inboard / down.
     Remember tumblehome: a side box can poke out the TOP corner too.
   - *collision* → two envelopes intersect; re-place one.
   - *mass closure* → the fabricated + COTS total is off MTOW; revisit the
     decomposition or masses.
   - *retrieval* → a serviceable item isn't reachable through any opening,
     or a fixed box blocks the pull corridor; clear the channel.

4. **Re-run.** Repeat until 0 FAIL. WARN is allowed for honest, documented
   compromises; FAIL is not.

5. **Verify the boolean, don't trust it.** When the layout drives real
   geometry (cuts, mounts, decks), the build must export the as-built result
   and an audit must assert its expected bbox/volume/CG — because the
   kernel can silently no-op a boolean (see GUARDRAILS.md §1).

## Containment guardrail (the one that bites)

Check containment against the REAL exported section/ring
(`out/sections.json`), NOT an assumed beam. The solver template falls back
to the design envelope only on a fresh scaffold and WARNs about it — wire it
to the real ring as soon as the build exports one. Mounting hardware buried
in the skin is forbidden: a 6 mm visual skin on a steep wall can leave only
a few mm to the exterior, which viz decimation can eat.

## Where the loop lives in the methodology

This is the cheapest-fidelity layer of design iteration: placements and
boxes, no rebuild. When a fork is genuinely open (where to put the battery),
escalate to `run-tradeoff-study` (scored + sensitivity). When the winner is
chosen, the full build + `audit.py` verifies the as-built result.
