---
name: add-material
description: >-
  Add or edit a material in a hardware-as-code project's cited material
  source-of-truth (design/materials.json). Use whenever an analysis needs a
  material property (density, modulus, Poisson, yield/ultimate strength,
  composite lamina properties) — instead of letting the model invent one.
  Enforces: NEVER hallucinate; every property carries a primary-source
  citation (MMPDS / CMH-17 / ASM / manufacturer datasheet); composites cite
  the specific prepreg + fiber-volume-fraction + layup, never "generic CFRP";
  fluids come from CoolProp, not hardcoded. See GUARDRAILS.md §8.
---

# add-material

Material properties are where a model hallucinates most dangerously — a wrong
modulus or a generic "CFRP" strength silently poisons every FEA and mass/CG
audit. This skill keeps them honest: **`design/materials.json` is the source of
truth, and nothing goes in it without a citation.**

## Rules (non-negotiable)

1. **Never invent a value.** If you don't have a primary source, say so and ask
   the user — do not fill a plausible number.
2. **Cite the source** for every material: MMPDS (metals), CMH-17 (composites),
   an ASM handbook, or a manufacturer datasheet (alloy **and** temper, or the
   specific prepreg). Record it in the `source` field.
3. **`verified` flag.** Set `verified: false` for "typical"/unconfirmed values;
   set `true` only after a human checks it against the cited source. The
   `guardrails-check` skill flags any audit input that is missing or unverified.
4. **Composites:** one entry per prepreg+layup, named accordingly (e.g.
   `T700-2510-UD-Vf57-quasi-iso`). Cite Vf, layup, orientation; record
   anisotropy (E1/E2/G12/ν12, directional strengths). Generic "CFRP" is forbidden.
5. **Allowables, not typicals,** for safety-critical margins — prefer A-/B-basis
   statistical allowables over handbook averages.
6. **Fluids** (CFD): never hardcode density/viscosity. Pull from CoolProp at the
   real T/P, e.g. `PropsSI('D','T',288.15,'P',101325,'Air')`.

## Procedure

1. Read `design/materials.json`. If the material already exists, reuse it.
2. Obtain real values from a citable source. No source → stop and ask the user.
3. Add the entry with SI units, the `source` citation, and `verified` set
   honestly. For composites, include the prepreg/Vf/layup and directional props.
4. Make audits (`fea*`, mass/CG) read the property FROM `materials.json` — never
   inline the number in a script.
5. Run `guardrails-check`: it should report zero audit-used properties that are
   missing or `verified: false` (or surface them for the user to confirm).

## Why

There is no free, comprehensive, machine-readable database of engineering design
*allowables*: MMPDS/CMH-17/ASM/Granta are paid; the open ones (Materials
Project, PAULING FILE) hold computed crystallographic data, not 6061-T6 yield.
So the project carries its own small, **cited** database — the same discipline as
`[PUB]`-tagged geometry in design.json.
