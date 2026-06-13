# /// script
# dependencies = [
#   "matplotlib",
#   "numpy",
#   "pillow",
#   "pyvista",
# ]
# ///

from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import io
import json
import os
import struct

import matplotlib

matplotlib.use("Agg")

from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# Model sources and licenses:
# - aircraft: NASA Airborne Science Program, "B777 - LaRC",
#   https://airbornescience.nasa.gov/3d-models/ and direct model
#   https://airbornescience.nasa.gov/3d-models/models/B777_LARC_AIR_0626.glb
#   License/use: NASA media guidelines. NASA 3D model polygon data and texture
#   maps are generally not subject to copyright in the United States; NASA
#   should be acknowledged and endorsement must not be implied.
# - spacecraft: NASA/JPL-Caltech, "Mars Reconnaissance Orbiter, 3D Model",
#   https://science.nasa.gov/resource/mars-reconnaissance-orbiter-3d-model/
#   direct model:
#   https://assets.science.nasa.gov/content/dam/science/psd/mars/resources/gltf_files/24884_MRO.glb
#   License/use: NASA media guidelines. NASA 3D model polygon data and texture
#   maps are generally not subject to copyright in the United States; NASA
#   should be acknowledged and endorsement must not be implied.
# - truck: Artec 3D, "Semi-trailer truck",
#   https://www.artec3d.com/3d-models/semi-trailer-truck and direct model
#   https://cdn.artec3d.com/content-hub-3dmodels/truck.zip?VersionId=rXdmdvKc7U9APKSKOVXygNcqO8QEWe5a
#   License/use: Creative Commons Attribution 3.0 Unported, attribution to
#   Artec 3D. The extracted archive also includes truck/license.txt.


WIDTH = 1600
HEIGHT = 800
DPI = 100
BG = "#0d1117"
BG_RGB = (13, 17, 23)
INK = "#e6edf3"
FG = "#c9d1d9"
MUTED = "#8b949e"
GRID = "#30363d"
ACCENT = "#58a6ff"
MODEL_DIR = Path(__file__).resolve().parent / "models"
COLUMN_LEFTS = (0, WIDTH // 3, (WIDTH * 2) // 3, WIDTH)
MODEL_Y = 92
LABEL_Y = 570
CHART_PANEL_SIZE = (462, 148)


@dataclass(frozen=True)
class ModelAudit:
    key: str
    title: str
    path: str
    source_url: str
    license: str
    triangles: int
    render_triangles: int | None = None


@dataclass(frozen=True)
class Rendered:
    aircraft: Image.Image
    spacecraft: Image.Image
    truck: Image.Image
    audits: tuple[ModelAudit, ...]


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        header = fh.read(24)
    return struct.unpack(">II", header[16:24])


def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
        alpha,
    )


def load_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    props = font_manager.FontProperties(family="DejaVu Sans", weight=weight)
    path = font_manager.findfont(props, fallback_to_default=True)
    return ImageFont.truetype(path, size=size)


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"required real model file missing: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"required real model file is empty: {path}")
    return path


def make_background() -> Image.Image:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    base = np.array(BG_RGB, dtype=float)
    vertical = (1.0 - yy / HEIGHT)[:, :, None] * np.array([7.0, 9.0, 12.0])
    diagonal = np.clip(1.0 - (0.62 * xx / WIDTH + 0.85 * yy / HEIGHT), 0, 1)[:, :, None]
    diagonal = diagonal * np.array([10.0, 14.0, 18.0])
    lower_band = np.exp(-((yy - 690) / 180) ** 2)[:, :, None] * np.array([3.0, 5.0, 7.0])
    rng = np.random.default_rng(31)
    noise = rng.normal(0, 1.25, size=(HEIGHT, WIDTH, 1))
    arr = np.clip(base + vertical + diagonal + lower_band + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def add_background_lines(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    for y, alpha in ((132, 38), (584, 32), (716, 34)):
        draw.line((88, y, WIDTH - 88, y), fill=hex_to_rgba(GRID, alpha), width=1)
    for x in COLUMN_LEFTS[1:-1]:
        draw.line((x, 170, x, 618), fill=hex_to_rgba(GRID, 16), width=1)
    for x in range(110, WIDTH - 80, 120):
        draw.line((x, 728, x + 34, 728), fill=hex_to_rgba(GRID, 22), width=1)


def paste_with_shadow(base: Image.Image, overlay: Image.Image, xy: tuple[int, int], shadow_offset=(0, 22)) -> None:
    overlay = overlay.convert("RGBA")
    alpha = overlay.getchannel("A")
    if alpha.getextrema() == (255, 255):
        base.alpha_composite(overlay, xy)
        return
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(26)).point(lambda p: int(p * 0.45))
    shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    base.alpha_composite(shadow, (xy[0] + shadow_offset[0], xy[1] + shadow_offset[1]))
    base.alpha_composite(overlay, xy)


def resize_render(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)


def setup_pyvista(size: tuple[int, int]):
    import pyvista as pv

    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    pv.OFF_SCREEN = True
    pv.global_theme.background = BG
    pv.global_theme.font.color = FG
    plotter = pv.Plotter(off_screen=True, window_size=(size[0] * 2, size[1] * 2), lighting="none")
    plotter.set_background(BG)
    try:
        plotter.enable_anti_aliasing("ssaa")
    except Exception:
        plotter.enable_anti_aliasing("msaa")
    try:
        plotter.enable_eye_dome_lighting()
    except Exception:
        pass
    return plotter, pv


def add_lighting(plotter, pv, key=(5.0, -6.0, 5.0), fill=(-4.0, 3.0, 3.0), rim=(0.0, 5.0, 4.0)) -> None:
    plotter.add_light(pv.Light(position=key, focal_point=(0, 0, 0), intensity=1.22, color="#ffffff"))
    plotter.add_light(pv.Light(position=fill, focal_point=(0, 0, 0), intensity=0.44, color="#9ecbff"))
    plotter.add_light(pv.Light(position=rim, focal_point=(0, 0, 0), intensity=0.32, color="#d2a8ff"))


def scalar_bar_args(title: str, pos=(0.86, 0.22), height=0.50) -> dict:
    return {
        "title": title,
        "title_font_size": 18,
        "label_font_size": 14,
        "n_labels": 4,
        "fmt": "%.2g",
        "color": FG,
        "position_x": pos[0],
        "position_y": pos[1],
        "width": 0.050,
        "height": height,
        "vertical": True,
        "font_family": "arial",
    }


def screenshot_plotter(plotter, final_size: tuple[int, int]) -> Image.Image:
    arr = plotter.screenshot(return_img=True, transparent_background=True)
    plotter.close()
    mode = "RGB" if arr.ndim == 3 and arr.shape[2] == 3 else "RGBA"
    image = Image.fromarray(arr, mode).convert("RGBA")
    return image.resize(final_size, Image.Resampling.LANCZOS)


def collect_surfaces(dataset) -> list:
    import pyvista as pv

    if isinstance(dataset, pv.MultiBlock):
        meshes = []
        for block in dataset:
            if block is not None:
                meshes.extend(collect_surfaces(block))
        return meshes
    if getattr(dataset, "n_points", 0) == 0:
        return []
    return [dataset.extract_surface(algorithm="dataset_surface").triangulate()]


def merge_meshes(meshes: list):
    if not meshes:
        raise ValueError("model loaded but did not contain polygonal mesh data")
    mesh = meshes[0].copy(deep=True)
    for other in meshes[1:]:
        mesh = mesh.merge(other, merge_points=False)
    return safe_normals(mesh.clean().triangulate())


def safe_normals(mesh):
    try:
        return mesh.compute_normals(
            point_normals=True,
            cell_normals=False,
            consistent_normals=True,
            auto_orient_normals=True,
            non_manifold_traversal=False,
        )
    except Exception:
        return mesh


def load_pyvista_model(path: Path):
    import pyvista as pv

    require_file(path)
    dataset = pv.read(path)
    mesh = merge_meshes(collect_surfaces(dataset))
    if mesh.n_cells <= 0 or mesh.n_points <= 0:
        raise ValueError(f"model did not load into usable triangles: {path}")
    return mesh


def normalize_points(points: np.ndarray, axes: tuple[int, int, int], target_extent: float) -> np.ndarray:
    pts = points[:, axes].astype(float, copy=True)
    center = (pts.min(axis=0) + pts.max(axis=0)) / 2.0
    pts -= center
    max_extent = float((pts.max(axis=0) - pts.min(axis=0)).max())
    if max_extent <= 0:
        raise ValueError("mesh has zero extent after loading")
    pts *= target_extent / max_extent
    return pts


def orient_mesh(mesh, axes: tuple[int, int, int], target_extent: float, flip_x: bool = False, z_offset: float = 0.0):
    out = mesh.copy(deep=True)
    pts = normalize_points(out.points, axes, target_extent)
    if flip_x:
        pts[:, 0] *= -1
    pts[:, 2] += z_offset
    out.points = pts
    return safe_normals(out)


def aircraft_cp(points: np.ndarray) -> np.ndarray:
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    x0 = (x - x.min()) / max(float(x.max() - x.min()), 1e-9)
    y_abs = np.abs(y)
    span = max(float(y_abs.max()), 1e-9)
    top = np.clip((z - np.percentile(z, 42)) / max(np.ptp(z), 1e-9), 0, 1)
    nose_pressure = 1.05 * np.exp(-((x0 - 0.98) / 0.12) ** 2 - (y_abs / 0.75) ** 2)
    wing_band = np.exp(-(((y_abs / span) - 0.52) / 0.27) ** 2 - ((x0 - 0.50) / 0.32) ** 2)
    wing_suction = -1.28 * wing_band * (0.70 + 0.30 * top)
    wing_leading = 0.58 * np.exp(-(((y_abs / span) - 0.50) / 0.30) ** 2 - ((x0 - 0.67) / 0.13) ** 2)
    fuselage_suction = -0.82 * np.exp(-((x0 - 0.56) / 0.34) ** 2) * (0.35 + 0.65 * top)
    tail = -0.45 * np.exp(-((x0 - 0.12) / 0.16) ** 2 - (y_abs / 0.72) ** 2)
    ripple = 0.14 * np.sin(4.2 * y + 1.4 * x)
    return np.clip(nose_pressure + wing_suction + wing_leading + fuselage_suction + tail + ripple, -1.65, 1.10)


def mro_vm(points: np.ndarray) -> np.ndarray:
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    x_abs = np.abs(x)
    x_span = max(float(x_abs.max()), 1e-9)
    y_span = max(float(np.abs(y).max()), 1e-9)
    z_span = max(float(np.ptp(z)), 1e-9)
    core = 112.0 * np.exp(-(x / 1.18) ** 2 - (y / 1.05) ** 2 - (z / 1.25) ** 2)
    panel_roots = 175.0 * np.exp(-((x_abs - 1.08) / 0.38) ** 2 - (y / 0.72) ** 2 - ((z - 0.16) / 1.4) ** 2)
    panel_modes = 84.0 * (x_abs / x_span) ** 1.35 * (0.48 + 0.52 * np.sin(2.9 * x + 1.1 * z) ** 2)
    antenna = 128.0 * np.exp(-((y + 0.56 * y_span) / 0.64) ** 2 - ((x + 0.15) / 1.55) ** 2 - ((z + 0.12 * z_span) / 1.10) ** 2)
    bus_corners = 62.0 * (np.sin(2.6 * x) ** 2 + 0.58 * np.cos(3.2 * y + 0.7 * z) ** 2)
    return np.clip(45.0 + core + panel_roots + panel_modes + antenna + bus_corners, 45, 420)


def truck_q(points: np.ndarray) -> np.ndarray:
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    x0 = (x - x.min()) / max(float(x.max() - x.min()), 1e-9)
    z0 = (z - z.min()) / max(float(z.max() - z.min()), 1e-9)
    stagnation = 0.94 * np.exp(-((x0 - 0.96) / 0.10) ** 2 - (y / 0.58) ** 2 - ((z0 - 0.48) / 0.38) ** 2)
    roof = 0.36 * np.exp(-((z0 - 0.88) / 0.16) ** 2 - ((x0 - 0.72) / 0.24) ** 2)
    wake = -0.52 * np.exp(-((x0 - 0.05) / 0.17) ** 2 - (z0 / 0.50) ** 2)
    flank = 0.16 * np.cos(2.9 * y) + 0.10 * np.sin(5.0 * x0)
    return np.clip(stagnation + roof + wake + flank, -0.58, 1.30)


def add_scalar(mesh, name: str, values: np.ndarray):
    out = mesh.copy(deep=True)
    out.point_data[name] = values.astype(np.float32)
    return out


def render_mesh(
    mesh,
    scalar: str,
    cmap: str,
    clim: tuple[float, float],
    bar_title: str,
    size: tuple[int, int],
    camera_position,
    zoom: float,
    bar_pos=(0.86, 0.22),
    bar_height=0.50,
    show_edges: bool = False,
) -> Image.Image:
    plotter, pv = setup_pyvista(size)
    add_lighting(plotter, pv)
    plotter.add_mesh(
        mesh,
        scalars=scalar,
        cmap=cmap,
        clim=clim,
        smooth_shading=True,
        split_sharp_edges=True,
        pbr=True,
        metallic=0.04,
        roughness=0.46,
        ambient=0.18,
        diffuse=0.72,
        specular=0.36,
        specular_power=34,
        show_edges=show_edges,
        edge_color="#dbe7ff",
        line_width=0.16,
        scalar_bar_args=scalar_bar_args(bar_title, pos=bar_pos, height=bar_height),
    )
    plotter.camera_position = camera_position
    plotter.camera.zoom(zoom)
    return screenshot_plotter(plotter, size)


def build_truck_cache(obj_path: Path, cache_path: Path, meta_path: Path, cell: float = 60.0):
    import pyvista as pv

    require_file(obj_path)
    print(f"building truck render mesh cache from {obj_path.name} at {cell:g} mm cells")
    vertex_map = array("I", [0])
    clusters: dict[tuple[int, int, int], int] = {}
    sums: list[list[float]] = []
    counts: list[int] = []
    original_vertices = 0

    with obj_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("v "):
                continue
            _, xs, ys, zs = line.split()[:4]
            x, y, z = float(xs), float(ys), float(zs)
            key = (round(x / cell), round(y / cell), round(z / cell))
            idx = clusters.get(key)
            if idx is None:
                idx = len(sums)
                clusters[key] = idx
                sums.append([x, y, z])
                counts.append(1)
            else:
                sums[idx][0] += x
                sums[idx][1] += y
                sums[idx][2] += z
                counts[idx] += 1
            vertex_map.append(idx)
            original_vertices += 1

    points = np.asarray(sums, dtype=np.float32)
    points /= np.asarray(counts, dtype=np.float32)[:, None]

    seen: set[tuple[int, int, int]] = set()
    faces: list[tuple[int, int, int]] = []
    original_triangles = 0
    degenerate = 0

    def obj_index(token: str) -> int:
        raw = int(token.split("/")[0])
        return raw if raw >= 0 else original_vertices + raw + 1

    with obj_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("f "):
                continue
            vertices = [vertex_map[obj_index(part)] for part in line.split()[1:]]
            if len(vertices) < 3:
                continue
            for i in range(1, len(vertices) - 1):
                tri = (vertices[0], vertices[i], vertices[i + 1])
                original_triangles += 1
                if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
                    degenerate += 1
                    continue
                key = tuple(sorted(tri))
                if key in seen:
                    continue
                seen.add(key)
                faces.append(tri)

    face_data = np.empty((len(faces), 4), dtype=np.int64)
    face_data[:, 0] = 3
    face_data[:, 1:] = np.asarray(faces, dtype=np.int64)
    mesh = safe_normals(pv.PolyData(points, face_data.ravel()).clean().triangulate())
    mesh.save(cache_path)
    meta = {
        "source": str(obj_path),
        "cell_mm": cell,
        "original_vertices": original_vertices,
        "original_triangles": original_triangles,
        "degenerate_after_clustering": degenerate,
        "render_vertices": int(mesh.n_points),
        "render_triangles": int(mesh.n_cells),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return mesh, meta


def load_truck_render_mesh():
    import pyvista as pv

    obj_path = MODEL_DIR / "truck" / "Truck.obj"
    cache_path = MODEL_DIR / "truck" / "Truck_clustered_60mm.vtp"
    meta_path = MODEL_DIR / "truck" / "Truck_clustered_60mm.json"
    if cache_path.exists() and meta_path.exists():
        mesh = pv.read(cache_path).extract_surface(algorithm="dataset_surface").triangulate()
        if mesh.n_cells <= 0:
            raise ValueError(f"cached truck mesh is invalid: {cache_path}")
        return safe_normals(mesh), json.loads(meta_path.read_text())
    return build_truck_cache(obj_path, cache_path, meta_path)


def render_aircraft() -> tuple[Image.Image, ModelAudit]:
    path = MODEL_DIR / "b777_larc_air_0626.glb"
    mesh = orient_mesh(load_pyvista_model(path), axes=(2, 0, 1), target_extent=5.5, flip_x=False)
    mesh = add_scalar(mesh, "Cp", aircraft_cp(mesh.points))
    image = render_mesh(
        mesh,
        scalar="Cp",
        cmap="coolwarm",
        clim=(-1.65, 1.10),
        bar_title="Cp",
        size=(690, 505),
        camera_position=[(5.7, -5.9, 3.0), (0.05, 0.0, 0.05), (0, 0, 1)],
        zoom=1.08,
        bar_pos=(0.865, 0.22),
        bar_height=0.48,
    )
    return image, ModelAudit(
        key="aircraft",
        title="NASA B777 - LaRC",
        path=str(path.relative_to(Path(__file__).resolve().parent)),
        source_url="https://airbornescience.nasa.gov/3d-models/models/B777_LARC_AIR_0626.glb",
        license="NASA media guidelines; generally not subject to US copyright",
        triangles=int(mesh.n_cells),
    )


def render_spacecraft() -> tuple[Image.Image, ModelAudit]:
    path = MODEL_DIR / "mars_reconnaissance_orbiter_a.glb"
    mesh = orient_mesh(load_pyvista_model(path), axes=(0, 1, 2), target_extent=5.0, flip_x=False, z_offset=-0.05)
    mesh = add_scalar(mesh, "vm", mro_vm(mesh.points))
    image = render_mesh(
        mesh,
        scalar="vm",
        cmap="turbo",
        clim=(45, 420),
        bar_title="MPa",
        size=(620, 500),
        camera_position=[(5.3, -5.9, 3.45), (0, 0, 0.05), (0, 0, 1)],
        zoom=1.12,
        bar_pos=(0.895, 0.25),
        bar_height=0.44,
        show_edges=True,
    )
    return image, ModelAudit(
        key="spacecraft",
        title="NASA Mars Reconnaissance Orbiter GLB",
        path=str(path.relative_to(Path(__file__).resolve().parent)),
        source_url="https://science.nasa.gov/resource/mars-reconnaissance-orbiter-3d-model/",
        license="NASA/JPL-Caltech; NASA media guidelines",
        triangles=int(mesh.n_cells),
    )


def render_truck() -> tuple[Image.Image, ModelAudit]:
    mesh, meta = load_truck_render_mesh()
    mesh = orient_mesh(mesh, axes=(1, 0, 2), target_extent=5.6, flip_x=False, z_offset=-0.28)
    mesh = add_scalar(mesh, "q", truck_q(mesh.points))
    image = render_mesh(
        mesh,
        scalar="q",
        cmap="viridis",
        clim=(-0.58, 1.30),
        bar_title="q",
        size=(620, 440),
        camera_position=[(5.0, -5.1, 2.8), (0.04, 0, 0.28), (0, 0, 1)],
        zoom=1.08,
        bar_pos=(0.045, 0.24),
        bar_height=0.44,
    )
    return image, ModelAudit(
        key="truck",
        title="Artec 3D Semi-trailer truck",
        path="models/truck/Truck.obj",
        source_url="https://www.artec3d.com/3d-models/semi-trailer-truck",
        license="Creative Commons Attribution 3.0 Unported; attribute Artec 3D",
        triangles=int(meta["original_triangles"]),
        render_triangles=int(meta["render_triangles"]),
    )


def render_all() -> Rendered:
    aircraft, aircraft_audit = render_aircraft()
    spacecraft, spacecraft_audit = render_spacecraft()
    truck, truck_audit = render_truck()
    return Rendered(aircraft, spacecraft, truck, (aircraft_audit, spacecraft_audit, truck_audit))


def mpl_render_to_image(fig: plt.Figure) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, transparent=True, facecolor=(0, 0, 0, 0), edgecolor=(0, 0, 0, 0))
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


def style_chart_axis(ax: plt.Axes) -> None:
    ax.set_facecolor((0, 0, 0, 0))
    ax.tick_params(axis="both", colors=MUTED, labelsize=6, width=0.45, length=2.5, pad=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(0.55)
    ax.grid(True, which="major", axis="y", color=GRID, linewidth=0.45, alpha=0.35)


def render_charts(size=(510, 136)) -> Image.Image:
    w, h = size
    fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI, facecolor=(0, 0, 0, 0))
    ax1 = fig.add_axes([0.07, 0.24, 0.41, 0.62])
    ax2 = fig.add_axes([0.57, 0.24, 0.38, 0.62])
    for ax in (ax1, ax2):
        style_chart_axis(ax)

    iterations = np.arange(1, 96)
    residual = np.exp(-iterations / 13.5) * (1 + 0.10 * np.sin(iterations * 0.38)) + 1.4e-4
    ax1.semilogy(iterations, residual, color=ACCENT, linewidth=1.35)
    ax1.set_xlim(1, 95)
    ax1.set_ylim(1e-4, 1)
    ax1.set_xticks([1, 45, 90])
    ax1.set_yticks([1e-4, 1e-2, 1])
    ax1.set_yticklabels(["1e-4", "1e-2", "1"])
    ax1.text(0.02, 0.91, "residual", transform=ax1.transAxes, color=MUTED, fontsize=7)

    t = np.linspace(0, 12, 260)
    load = 0.48 + 0.24 * np.sin(1.18 * t) + 0.22 * ((t > 3.2) & (t < 8.6))
    response = 0.44 + 0.20 * np.sin(1.18 * t - 0.58) + 0.17 * (1 - np.exp(-0.68 * np.maximum(t - 3.2, 0)))
    response -= 0.12 * (1 - np.exp(-1.05 * np.maximum(t - 8.6, 0)))
    ax2.plot(t, load, color="#3fb950", linewidth=1.2)
    ax2.plot(t, response, color="#d2a8ff", linewidth=1.2)
    ax2.set_xlim(0, 12)
    ax2.set_ylim(0.05, 1.08)
    ax2.set_xticks([0, 6, 12])
    ax2.set_yticks([0.25, 0.85])
    ax2.text(0.02, 0.91, "load", transform=ax2.transAxes, color="#3fb950", fontsize=7)
    ax2.text(0.28, 0.91, "resp", transform=ax2.transAxes, color="#d2a8ff", fontsize=7)
    return mpl_render_to_image(fig)


def draw_text_layer(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    label_font = load_font(13, "regular")
    small_font = load_font(11, "regular")
    wordmark_font = load_font(15, "regular")
    labels = [
        ((COLUMN_LEFTS[0] + 92, LABEL_Y), "cfd", "surface pressure"),
        ((COLUMN_LEFTS[1] + 92, LABEL_Y), "fea", "von-mises stress"),
        ((COLUMN_LEFTS[2] + 92, LABEL_Y), "telemetry", "residual + load"),
    ]
    for (x, y), main, detail in labels:
        draw.text((x, y), main, fill=hex_to_rgba(INK, 224), font=label_font)
        draw.text((x, y + 20), detail, fill=hex_to_rgba(MUTED, 176), font=small_font)
    draw.text((92, 736), "agentic-digital-twin", fill=hex_to_rgba(MUTED, 214), font=wordmark_font)
    draw.line((92, 729, 231, 729), fill=hex_to_rgba(GRID, 90), width=1)


def centered_column_xy(column: int, size: tuple[int, int], y: int = MODEL_Y) -> tuple[int, int]:
    left = COLUMN_LEFTS[column]
    right = COLUMN_LEFTS[column + 1]
    return (left + (right - left - size[0]) // 2, y)


def composite(rendered: Rendered) -> Image.Image:
    canvas = make_background()
    draw = ImageDraw.Draw(canvas, "RGBA")

    aircraft_size = (515, 480)
    spacecraft_size = (515, 480)
    truck_size = (515, 420)
    aircraft = resize_render(rendered.aircraft, aircraft_size)
    spacecraft = resize_render(rendered.spacecraft, spacecraft_size)
    truck = resize_render(rendered.truck, truck_size)
    charts = render_charts((430, 118))

    paste_with_shadow(canvas, aircraft, centered_column_xy(0, aircraft_size))
    paste_with_shadow(canvas, spacecraft, centered_column_xy(1, spacecraft_size))
    paste_with_shadow(canvas, truck, centered_column_xy(2, truck_size, y=118))

    chart_panel = Image.new("RGBA", CHART_PANEL_SIZE, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(chart_panel, "RGBA")
    panel_draw.rounded_rectangle(
        (0, 0, CHART_PANEL_SIZE[0] - 1, CHART_PANEL_SIZE[1] - 1),
        radius=8,
        fill=(9, 13, 19, 172),
        outline=hex_to_rgba(GRID, 122),
        width=1,
    )
    chart_panel.alpha_composite(charts, (16, 15))
    canvas.alpha_composite(chart_panel, (WIDTH - CHART_PANEL_SIZE[0] - 24, 610))

    draw_text_layer(canvas)
    return canvas


def print_audit(audits: tuple[ModelAudit, ...]) -> None:
    for audit in audits:
        count = f"{audit.triangles:,}"
        if audit.render_triangles is not None:
            count = f"{count} source; {audit.render_triangles:,} render-cache"
        print(f"{audit.key}: {audit.title}")
        print(f"  file: {audit.path}")
        print(f"  triangles: {count}")
        print(f"  source: {audit.source_url}")
        print(f"  license: {audit.license}")


def main() -> None:
    out = Path(__file__).resolve().with_name("hero.png")
    rendered = render_all()
    image = composite(rendered).convert("RGB")
    image.save(out, "PNG", optimize=True)
    width, height = png_size(out)
    print_audit(rendered.audits)
    print("renderer: pyvista/vtk off-screen")
    print(f"wrote {out} ({width}x{height}px)")


if __name__ == "__main__":
    main()
