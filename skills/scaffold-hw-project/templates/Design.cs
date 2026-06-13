// Design.cs — build-source MIRROR of design/design.json.
//
// METHODOLOGY RULE: design.json is the SINGLE SOURCE OF TRUTH. This file
// mirrors the subset of constants the geometry build needs. Update the JSON
// FIRST, then mirror the changed values here. NEVER let the two drift:
// audit.py reads design.json, the build reads this, and a mismatch is a
// silent-wrong-geometry bug waiting to happen.
//
// The build's Program.cs must EXPORT every geometry result it computes to
// out/*.json (components.json, contacts.json, sections.json, ...). Audits
// read those exports — they never re-derive geometry. That is what keeps
// "geometry is code" honest.
//
// If your kernel is Python (build123d / CadQuery / OpenSCAD-via-SolidPython),
// rename this to design_mirror.py and translate the constants verbatim.
//
// PicoGK reminder (if using the LEAP71 stack): run with
//   DOTNET_ROLL_FORWARD=LatestMajor dotnet run
// Headless: new Library(voxelMM) + Library.RegisterGlobalLibrary(lib).

namespace Project
{
    public static class Design
    {
        // ---- coordinate system -------------------------------------------
        public const float VOXEL_MM = 2.0f;     // mirror coordinate_system.voxel_mm
        public const float MIN_WALL_MM = 4.0f;  // ~2 voxels; thinner walls vanish/perforate

        // ---- primary body (mirror geometry.primary_body) -----------------
        public const float BODY_LEN_MM = 1000.0f;
        public const float BODY_WID_MM = 200.0f;
        public const float BODY_HGT_MM = 150.0f;
        public const float SKIN_VISUAL_MM = 6.0f;

        // ---- masses (mirror masses_kg.*.mass; CG closes in audit.py) -----
        public const float MTOW_KG = 10.0f;

        // Add the rest of the mirrored constants here as the design grows.
        // Each one MUST have a matching entry in design/design.json.
    }
}
