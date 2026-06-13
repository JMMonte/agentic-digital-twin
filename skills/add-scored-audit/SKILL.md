---
name: add-scored-audit
description: >-
  Add a new executable scored check (PASS/WARN/FAIL) for a requirement to a
  hardware-as-code project's audit harness. Use when a requirement,
  clearance, mass budget, margin, or anchor needs to be verified
  automatically. Enforces the rules: read the build's exported JSON
  artifacts, never duplicate a geometry constant, assert an EXPECTED value
  (not just ">0"), and exit 1 on FAIL.
---

# Add a scored audit check

A requirement that is not in an audit is a requirement that will silently
regress. This skill adds one check the right way.

## The rules a check must follow

1. **Read, don't redeclare.** Pull the value from `design/design.json` or a
   build-exported `out/*.json` artifact. NEVER hard-code a geometry constant
   in the audit (regex it from the build source or read the JSON). A
   duplicated constant drifts and the audit then verifies a fiction.
2. **Assert an EXPECTED value, not existence.** The gold guardrail: a wrong
   boolean still passes `watertight` + `volume>0`. So check that the
   as-built bbox / volume / CG / margin matches a known anchor within a
   tolerance — not merely that it is positive.
3. **Three outcomes.** PASS, WARN (an HONEST, documented shortfall —
   e.g. physics contradicting a marketing claim), or FAIL (a real violation
   that must gate). Never use WARN to bury a real FAIL.
4. **Cross-check against an anchor.** A derived number is only trustworthy
   when it agrees with an independent truth: a published `[PUB]` value, an
   analytic formula, or the REAL exported artifact.

## Procedure

1. Open the project's `audit.py`. Identify (or add) the right section header
   (`sec = "N section name"`).

2. Find the source of truth for the value being checked:
   - a `[PUB]` anchor or requirement in `design/design.json`, or
   - a build-exported artifact in `out/` (bbox, volume, contact, section).
   If the build does not yet export what you need, add the export to the
   build FIRST (that is the source-of-truth discipline), then read it here.

3. Add the check. For a value-vs-anchor check, prefer the `expect()` helper:

   ```python
   sec = "2 clearances"
   prop_clearance = COMP["prop"]["bboxMin"][2] - deck_top_z   # from out/*.json
   req = D["requirements"]["prop_clearance_min_mm"]["min"]
   check(sec, "prop clears deck", prop_clearance >= req,
         f"clearance {prop_clearance:.1f} mm >= req {req} mm")
   ```

   For an as-built-matches-design check (the gold rule), assert the expected
   value, not just presence:

   ```python
   expect(sec, "tank volume as designed", built_vol_cm3,
          D["geometry"]["tank"]["volume_cm3"], tol=0.03 * design_vol, units=" cm3")
   ```

4. If the value maps to a score (for a tradeoff or a graded margin),
   remember the `np.interp` guardrail: ascending `xp`; lower-is-better uses
   ascending `xp` with REVERSED `fp`.

5. Run it: `uv run audit.py`. Confirm the new check appears in
   `out/audit_report.md` and that the exit code gates correctly (a real
   violation must exit 1).

6. If this check was added because something silently went wrong, also
   APPEND the lesson to `GUARDRAILS.md` and note which check now guards it.

## Anti-patterns to reject

- A check that re-types a dimension already in `design.json` (it will drift).
- `assert volume > 0` standing in for "the geometry is correct."
- A WARN on a real violation to make the report look green.
- A score that uses `np.interp` with a descending `xp`.
