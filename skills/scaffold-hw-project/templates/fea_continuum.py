# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "gmsh", "rerun-sdk>=0.23"]
# ///
"""Continuum FEA tier (tier 3): gmsh + CalculiX (ccx).

For continuum parts a beam model can't capture — brackets, fittings, lugs,
hull bottom panels, pressure shells, sponson roots. The cheaper tiers come
FIRST:
  tier 1  analytic checks in audit.py   (Euler buckling, beam bending, slam)
  tier 2  in-house numpy space-frame FEA (frames / trusses)
  tier 3  THIS: gmsh tet -> Abaqus .inp -> ccx -> parse -> VALIDATE -> rerun

THE DISCIPLINE (same as CFD — see GUARDRAILS.md §7): a continuum solve that
"ran clean" is NOT one that is correct. You VALIDATE against the tier below
BEFORE trusting it. This template solves a cantilever whose tip deflection
has a closed form (F·L^3 / 3EI) and GATES on matching it (exit 1 on FAIL).
Only once the anchor matches do you point the SAME pipeline at the real part
and run a mesh-convergence study. The canonical project anchor is a *BUCKLE
step whose first eigenvalue reproduces the audit's analytic Euler P_cr.

Headless: ccx (the solver) is pure CLI. cgx (GUI/post) needs XQuartz — never
depend on it; parse .dat / .frd and visualize in rerun.

Units: CalculiX is unit-AGNOSTIC. This deck is N, mm, MPa, tonne, t/mm^3.
A mixed system (mm geometry + E in Pa) silently scales stress by 10^x.

Run:  uv run fea_continuum.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

# --- locate the solver (FreeCAD bundles ccx 2.23; conda-forge is the CI pin) --
CCX = next((c for c in (shutil.which("ccx"),
                        "/Applications/FreeCAD.app/Contents/Resources/bin/ccx",
                        shutil.which("ccx_2.23")) if c and Path(c).exists()), None)
if not CCX:
    sys.exit("ccx not found. Install via `conda install -c conda-forge calculix` "
             "(osx-arm64 2.23) or use FreeCAD's bundled "
             "/Applications/FreeCAD.app/Contents/Resources/bin/ccx")

# --- problem (units: N, mm, MPa, tonne) ---------------------------------------
E, NU = 70000.0, 0.33          # MPa  (Al ~70 GPa = 70000 MPa)
L, W, H = 200.0, 20.0, 20.0    # mm   slender cantilever (L/H = 10)
F = 1000.0                     # N    tip load, -Z
MESH = 6.0                     # mm   target element size
TOL = 0.10                     # gate: FE tip deflection within 10% of analytic

# --- tier-1 analytic anchor (Euler-Bernoulli cantilever) ----------------------
I = W * H**3 / 12.0
delta_an = F * L**3 / (3.0 * E * I)        # tip deflection [mm] — CLEAN anchor
sigma_an = (F * L) * (H / 2.0) / I         # nominal root fibre stress [MPa]

# --- gmsh: quadratic-tet (C3D10) mesh of the bar ------------------------------
import gmsh
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.add("bar")
gmsh.model.occ.addBox(0, 0, 0, L, W, H)
gmsh.model.occ.synchronize()
gmsh.option.setNumber("Mesh.MeshSizeMin", MESH)
gmsh.option.setNumber("Mesh.MeshSizeMax", MESH)
gmsh.model.mesh.generate(3)
gmsh.model.mesh.setOrder(2)                # 2nd order -> tet10 (NOT C3D4: §7 lock)

ntags, ncoords, _ = gmsh.model.mesh.getNodes()
ncoords = ncoords.reshape(-1, 3)
xyz = {int(t): ncoords[i] for i, t in enumerate(ntags)}
etypes, etags, enodes = gmsh.model.mesh.getElements(dim=3)
conn = None
for et, tg, en in zip(etypes, etags, enodes):
    if et == 11:                           # gmsh type 11 = 10-node tetrahedron
        elem_tags = np.array(tg, dtype=int)
        conn = np.array(en, dtype=int).reshape(-1, 10)
gmsh.finalize()
if conn is None:
    sys.exit("no C3D10 tets meshed")

# gmsh tet10 -> Abaqus C3D10: corners identical, swap the last two mid nodes.
# THIS PERMUTATION IS THE GUARDRAIL (§7): wrong -> ccx negative Jacobian, or
# the analytic anchor fails LOUDLY (never silently).
def to_c3d10(r):
    r = list(r)
    return r[:8] + [r[9], r[8]]

fix = [t for t, p in xyz.items() if p[0] <= 1e-6]          # clamp x=0 face
tip = [t for t, p in xyz.items() if p[0] >= L - 1e-6]      # load x=L face

# --- write the Abaqus-style .inp deck -----------------------------------------
def nset(name, ids):
    out = [f"*NSET, NSET={name}"]
    out += [", ".join(map(str, ids[i:i + 8])) for i in range(0, len(ids), 8)]
    return out

work = Path(tempfile.mkdtemp(prefix="ccx_"))
job = work / "bar"
inp = ["*HEADING", "cantilever validation  units: N, mm, MPa, tonne", "*NODE"]
inp += [f"{t}, {p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f}" for t, p in xyz.items()]
inp.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
inp += [f"{int(tag)}, " + ", ".join(map(str, to_c3d10(row)))
        for tag, row in zip(elem_tags, conn)]
inp += nset("NALL", [int(t) for t in xyz]) + nset("FIX", fix) + nset("TIP", tip)
inp += ["*MATERIAL, NAME=MAT", "*ELASTIC", f"{E}, {NU}",
        "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT",
        "*STEP", "*STATIC",
        "*BOUNDARY", "FIX, 1, 3",
        "*CLOAD", f"TIP, 3, {-F / len(tip):.6f}",
        "*NODE PRINT, NSET=NALL", "U",
        "*EL PRINT, ELSET=EALL", "S",
        "*NODE FILE", "U", "*EL FILE", "S", "*END STEP"]
job.with_suffix(".inp").write_text("\n".join(inp) + "\n")

# --- run headless -------------------------------------------------------------
r = subprocess.run([CCX, "-i", str(job)], cwd=work, capture_output=True, text=True)
dat = job.with_suffix(".dat")
if r.returncode != 0 or not dat.exists():
    sys.exit(f"ccx failed (rc={r.returncode}). Tail:\n{r.stdout[-1500:]}")

# --- parse .dat (whitespace-tabular: easier + more robust than .frd) ----------
disp, vm_max = {}, 0.0
mode = None
for ln in dat.read_text().splitlines():
    s = ln.strip()
    low = s.lower()
    if low.startswith("displacements"):
        mode = "U"; continue
    if low.startswith("stresses"):
        mode = "S"; continue
    if not s or mode is None:
        continue                       # skip the blank between header and data; keep mode
    try:
        v = [float(x) for x in s.split()]
    except ValueError:
        continue                       # non-numeric line — skip, mode switches only on a header
    if mode == "U":
        disp[int(v[0])] = np.array(v[1:4])
    elif mode == "S" and len(v) >= 8:
        sxx, syy, szz, sxy, sxz, syz = v[2:8]
        vm_max = max(vm_max, np.sqrt(0.5 * ((sxx - syy)**2 + (syy - szz)**2
                     + (szz - sxx)**2) + 3 * (sxy**2 + sxz**2 + syz**2)))

delta_fe = max(np.linalg.norm(d) for d in disp.values())   # peak = tip
err = abs(delta_fe - delta_an) / delta_an

# --- gate on the CLEAN anchor (deflection); stress is informational -----------
# A fully-clamped face has a stress singularity at its edge, so peak von Mises
# OVERSHOOTS the nominal and won't converge there — do NOT gate on it. Gate on
# deflection (or a *BUCKLE eigenvalue on the real part).
ok = err <= TOL
print(f"analytic tip deflection : {delta_an:.4f} mm")
print(f"FE       tip deflection : {delta_fe:.4f} mm  ({err*100:.1f}% error)")
print(f"nominal root stress     : {sigma_an:.1f} MPa  (informational)")
print(f"FE peak von Mises       : {vm_max:.1f} MPa  (clamp singularity — informational)")
print(f"[{'PASS' if ok else 'FAIL'}] tier-3 (ccx) vs tier-1 anchor within {TOL*100:.0f}%")
print("NEXT: refine MESH until delta_fe stops moving (<~2-3%), THEN solve the real part.")

# --- visualize (rerun): deformed shape colored by displacement ----------------
try:
    import rerun as rr
    out = Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)
    rr.init("fea_continuum")
    rr.save(str(out / "fea_continuum.rrd"))
    ids = list(disp)
    P = np.array([xyz[i] for i in ids])
    U = np.array([disp[i] for i in ids])
    mag = np.linalg.norm(U, axis=1)
    col = (mag - mag.min()) / (np.ptp(mag) + 1e-9)
    colors = np.c_[col, 0.3 * np.ones_like(col), 1 - col]
    rr.log("undeformed", rr.Points3D(P, colors=[120, 120, 120], radii=0.6))
    scale = 0.2 * L / (mag.max() + 1e-9)            # exaggerate for visibility
    rr.log("deformed", rr.Points3D(P + scale * U, colors=colors, radii=0.8))
    print(f"viz: out/fea_continuum.rrd  (stream: uv run --with rerun-sdk python -m rerun out/fea_continuum.rrd)")
except Exception as e:
    print(f"(rerun viz skipped: {e})")

sys.exit(0 if ok else 1)
