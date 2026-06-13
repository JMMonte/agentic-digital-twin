# /// script
# dependencies = [
#   "matplotlib",
#   "numpy",
#   "pillow",
#   "pyvista",
# ]
# ///

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import io
import os
import struct
import traceback

import matplotlib

matplotlib.use("Agg")

from matplotlib import cm, font_manager
from matplotlib.colors import Normalize
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


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


@dataclass(frozen=True)
class RenderResult:
    renderer: str
    aircraft: Image.Image
    satellite: Image.Image
    truck: Image.Image


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


def make_background() -> Image.Image:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    base = np.array(BG_RGB, dtype=float)
    vertical = (1.0 - yy / HEIGHT)[:, :, None] * np.array([7.0, 9.0, 12.0])
    diagonal = np.clip(1.0 - (0.62 * xx / WIDTH + 0.85 * yy / HEIGHT), 0, 1)[:, :, None]
    diagonal = diagonal * np.array([10.0, 14.0, 18.0])
    lower_band = np.exp(-((yy - 690) / 180) ** 2)[:, :, None] * np.array([3.0, 5.0, 7.0])
    rng = np.random.default_rng(31)
    noise = rng.normal(0, 1.35, size=(HEIGHT, WIDTH, 1))
    arr = np.clip(base + vertical + diagonal + lower_band + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def add_background_lines(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    for y, alpha in ((132, 38), (584, 32), (716, 34)):
        draw.line((88, y, WIDTH - 88, y), fill=hex_to_rgba(GRID, alpha), width=1)
    for x in (472, 965, 1412):
        draw.line((x, 170, x, 618), fill=hex_to_rgba(GRID, 16), width=1)
    for x in range(110, WIDTH - 80, 120):
        draw.line((x, 728, x + 34, 728), fill=hex_to_rgba(GRID, 22), width=1)


def paste_with_shadow(base: Image.Image, overlay: Image.Image, xy: tuple[int, int], shadow_offset=(0, 22)) -> None:
    overlay = overlay.convert("RGBA")
    alpha = overlay.getchannel("A")
    extrema = alpha.getextrema()
    if extrema == (255, 255):
        base.alpha_composite(overlay, xy)
        return

    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(26)).point(lambda p: int(p * 0.45))
    shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    base.alpha_composite(shadow, (xy[0] + shadow_offset[0], xy[1] + shadow_offset[1]))
    base.alpha_composite(overlay, xy)


def resize_render(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)


def polydata_from_faces(points: list[list[float]], faces: list[int]):
    import pyvista as pv

    mesh = pv.PolyData(np.asarray(points, dtype=float), np.asarray(faces, dtype=np.int64))
    return mesh.clean().compute_normals(
        point_normals=True,
        cell_normals=True,
        consistent_normals=True,
        auto_orient_normals=True,
    )


def aircraft_cp(points: np.ndarray) -> np.ndarray:
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    top = np.maximum(z, 0)
    leading = 1.05 * np.exp(-((x - 2.58) / 0.40) ** 2 - (y / 0.58) ** 2)
    fuselage_suction = -1.25 * np.exp(-((x - 0.10) / 1.45) ** 2) * (0.22 + 0.78 * np.clip(top / 0.54, 0, 1))
    wing_upper = -1.18 * np.exp(-((np.abs(y) - 1.42) / 0.94) ** 2 - ((x + 0.58) / 1.18) ** 2)
    wing_upper *= 0.28 + 0.72 * np.clip((z + 0.02) / 0.30, 0, 1)
    wing_leading = 0.74 * np.exp(-((np.abs(y) - 1.18) / 1.08) ** 2 - ((x - 0.55) / 0.42) ** 2)
    wing_tip = 0.54 * np.exp(-((np.abs(y) - 2.12) / 0.46) ** 2 - ((x + 0.92) / 1.08) ** 2)
    tail = -0.62 * np.exp(-((x + 2.12) / 0.55) ** 2 - ((np.abs(y) - 0.62) / 0.44) ** 2)
    return np.clip(leading + fuselage_suction + wing_upper + wing_leading + wing_tip + tail + 0.10 * np.sin(2.8 * y), -1.65, 1.05)


def make_fuselage():
    points: list[list[float]] = []
    faces: list[int] = []
    xs = np.linspace(-3.05, 3.12, 88)
    theta = np.linspace(0, 2 * np.pi, 48, endpoint=False)

    for x in xs:
        s = (x - xs[0]) / (xs[-1] - xs[0])
        taper = np.sin(np.pi * s) ** 0.43
        taper *= 0.76 + 0.24 * np.cos(np.pi * (s - 0.42))
        taper = max(float(taper), 0.045)
        ry = 0.39 * taper * (1.0 + 0.08 * np.exp(-((s - 0.54) / 0.24) ** 2))
        rz = 0.46 * taper
        for t in theta:
            points.append([float(x), float(ry * np.cos(t)), float(rz * np.sin(t))])

    nt = len(theta)
    for i in range(len(xs) - 1):
        for j in range(nt):
            a = i * nt + j
            b = i * nt + (j + 1) % nt
            c = (i + 1) * nt + (j + 1) % nt
            d = (i + 1) * nt + j
            faces.extend([4, a, b, c, d])

    tail_center = len(points)
    points.append([float(xs[0] - 0.04), 0.0, 0.0])
    nose_center = len(points)
    points.append([float(xs[-1] + 0.04), 0.0, 0.0])
    for j in range(nt):
        faces.extend([3, tail_center, (j + 1) % nt, j])
        faces.extend([3, nose_center, (len(xs) - 1) * nt + j, (len(xs) - 1) * nt + (j + 1) % nt])

    mesh = polydata_from_faces(points, faces)
    mesh.point_data["Cp"] = aircraft_cp(mesh.points)
    return mesh


def make_swept_wing(
    side: float,
    root_y: float = 0.30,
    tip_y: float = 2.58,
    root_lead: float = 0.88,
    root_trail: float = -1.14,
    tip_lead: float = -0.38,
    tip_trail: float = -2.18,
    z_root: float = -0.01,
    dihedral: float = 0.18,
    thickness: float = 0.055,
    nspan: int = 38,
    nchord: int = 18,
):
    points: list[list[float]] = []
    faces: list[int] = []

    def point(eta: float, chord: float, top: bool) -> list[float]:
        y = side * (root_y + eta * (tip_y - root_y))
        lead = root_lead + eta * (tip_lead - root_lead)
        trail = root_trail + eta * (tip_trail - root_trail)
        x = lead + chord * (trail - lead)
        crown = 0.035 * np.sin(np.pi * chord) * (1 - 0.35 * eta)
        z = z_root + dihedral * eta + crown + (thickness / 2 if top else -thickness / 2)
        return [float(x), float(y), float(z)]

    for top in (True, False):
        start = len(points)
        for eta in np.linspace(0, 1, nspan):
            for chord in np.linspace(0, 1, nchord):
                points.append(point(float(eta), float(chord), top))
        for i in range(nspan - 1):
            for j in range(nchord - 1):
                a = start + i * nchord + j
                b = start + i * nchord + j + 1
                c = start + (i + 1) * nchord + j + 1
                d = start + (i + 1) * nchord + j
                faces.extend([4, a, b, c, d] if top else [4, a, d, c, b])

    top_start = 0
    bot_start = nspan * nchord
    for i in range(nspan - 1):
        for j0 in (0, nchord - 1):
            a = top_start + i * nchord + j0
            b = top_start + (i + 1) * nchord + j0
            c = bot_start + (i + 1) * nchord + j0
            d = bot_start + i * nchord + j0
            faces.extend([4, a, b, c, d])
    for i0 in (0, nspan - 1):
        for j in range(nchord - 1):
            a = top_start + i0 * nchord + j
            b = top_start + i0 * nchord + j + 1
            c = bot_start + i0 * nchord + j + 1
            d = bot_start + i0 * nchord + j
            faces.extend([4, a, b, c, d])

    mesh = polydata_from_faces(points, faces)
    mesh.point_data["Cp"] = aircraft_cp(mesh.points)
    return mesh


def make_vertical_tail():
    points: list[list[float]] = []
    faces: list[int] = []
    yvals = (-0.045, 0.045)
    profile = np.array(
        [
            [-2.42, 0.24],
            [-1.55, 0.25],
            [-1.83, 1.25],
            [-2.34, 0.86],
        ],
        dtype=float,
    )
    for y in yvals:
        for x, z in profile:
            points.append([float(x), float(y), float(z)])
    faces.extend([4, 0, 1, 2, 3])
    faces.extend([4, 4, 7, 6, 5])
    for i in range(4):
        faces.extend([4, i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i])
    mesh = polydata_from_faces(points, faces)
    mesh.point_data["Cp"] = aircraft_cp(mesh.points)
    return mesh


def box_scalar_aero(points: np.ndarray) -> np.ndarray:
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    stagnation = 1.2 * np.exp(-((x - 2.52) / 0.42) ** 2 - ((z - 0.52) / 0.55) ** 2)
    roof = 0.55 * np.exp(-((z - 1.08) / 0.22) ** 2 - ((x - 1.28) / 0.9) ** 2)
    wake = -0.55 * np.exp(-((x + 1.55) / 0.92) ** 2 - (z / 0.9) ** 2)
    flank = 0.22 * np.cos(2.7 * y) + 0.16 * z
    return np.clip(stagnation + roof + wake + flank, -0.55, 1.45)


def box_scalar_stress(points: np.ndarray) -> np.ndarray:
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    roots = 2.4 * np.exp(-((np.abs(x) - 0.67) / 0.16) ** 2 - (z / 0.56) ** 2)
    panel_modes = 0.55 * (np.sin(2.9 * x) ** 2 + 0.55 * np.cos(3.4 * z) ** 2)
    bus_corner = 1.1 * np.exp(-((np.abs(x) - 0.42) / 0.24) ** 2 - ((np.abs(z) - 0.34) / 0.18) ** 2)
    return 55 + 70 * panel_modes + 125 * roots + 70 * bus_corner + 18 * np.abs(y)


def make_subdivided_box(center, size, scalar_func, scalar_name: str, density=(10, 10, 10)):
    points: list[list[float]] = []
    faces: list[int] = []
    center = np.asarray(center, dtype=float)
    size = np.asarray(size, dtype=float)
    density = np.asarray(density, dtype=int)

    def add_face(axis: int, sign: float, u_axis: int, v_axis: int, nu: int, nv: int) -> None:
        start = len(points)
        fixed = center[axis] + sign * size[axis] / 2
        u_vals = np.linspace(center[u_axis] - size[u_axis] / 2, center[u_axis] + size[u_axis] / 2, nu)
        v_vals = np.linspace(center[v_axis] - size[v_axis] / 2, center[v_axis] + size[v_axis] / 2, nv)
        for v in v_vals:
            for u in u_vals:
                coord = center.copy()
                coord[axis] = fixed
                coord[u_axis] = u
                coord[v_axis] = v
                points.append([float(coord[0]), float(coord[1]), float(coord[2])])
        for j in range(nv - 1):
            for i in range(nu - 1):
                a = start + j * nu + i
                b = start + j * nu + i + 1
                c = start + (j + 1) * nu + i + 1
                d = start + (j + 1) * nu + i
                faces.extend([4, a, b, c, d] if sign > 0 else [4, a, d, c, b])

    nx, ny, nz = density
    add_face(0, 1, 1, 2, ny, nz)
    add_face(0, -1, 1, 2, ny, nz)
    add_face(1, 1, 0, 2, nx, nz)
    add_face(1, -1, 0, 2, nx, nz)
    add_face(2, 1, 0, 1, nx, ny)
    add_face(2, -1, 0, 1, nx, ny)

    mesh = polydata_from_faces(points, faces)
    mesh.point_data[scalar_name] = scalar_func(mesh.points)
    return mesh


def make_truck_cab():
    side = np.array(
        [
            [1.08, 0.00],
            [2.52, 0.00],
            [2.52, 0.62],
            [2.10, 1.04],
            [1.08, 1.04],
        ],
        dtype=float,
    )
    ys = (-0.50, 0.50)
    points: list[list[float]] = []
    faces: list[int] = []
    for y in ys:
        for x, z in side:
            points.append([float(x), float(y), float(z)])
    faces.extend([5, 0, 1, 2, 3, 4])
    faces.extend([5, 5, 9, 8, 7, 6])
    for i in range(len(side)):
        faces.extend([4, i, (i + 1) % len(side), len(side) + (i + 1) % len(side), len(side) + i])
    mesh = polydata_from_faces(points, faces)
    mesh.point_data["q"] = box_scalar_aero(mesh.points)
    return mesh


def setup_pyvista(size: tuple[int, int]):
    import pyvista as pv

    pv.OFF_SCREEN = True
    pv.global_theme.background = BG
    pv.global_theme.font.color = FG
    plotter = pv.Plotter(off_screen=True, window_size=size, lighting="none")
    plotter.set_background(BG)
    try:
        plotter.enable_anti_aliasing("ssaa")
    except Exception:
        try:
            plotter.enable_anti_aliasing("msaa")
        except Exception:
            pass
    try:
        plotter.enable_eye_dome_lighting()
    except Exception:
        pass
    return plotter, pv


def add_soft_lighting(plotter, pv, key=(5.0, -6.0, 5.0), fill=(-4.0, 3.0, 3.0)) -> None:
    plotter.add_light(pv.Light(position=key, focal_point=(0, 0, 0.25), intensity=0.95, color="#ffffff"))
    plotter.add_light(pv.Light(position=fill, focal_point=(0, 0, 0), intensity=0.35, color="#8ab4f8"))
    plotter.add_light(pv.Light(position=(0, -2, 6), focal_point=(0, 0, 0), intensity=0.22, color="#b5f5e0"))


def scalar_bar_args(title: str, pos=(0.86, 0.22), height=0.52) -> dict:
    return {
        "title": title,
        "title_font_size": 12,
        "label_font_size": 9,
        "n_labels": 4,
        "fmt": "%.2g",
        "color": FG,
        "position_x": pos[0],
        "position_y": pos[1],
        "width": 0.045,
        "height": height,
        "vertical": True,
        "font_family": "arial",
    }


def screenshot_plotter(plotter, transparent: bool = True) -> Image.Image:
    arr = plotter.screenshot(return_img=True, transparent_background=transparent)
    plotter.close()
    if arr.ndim == 3 and arr.shape[2] == 3:
        return Image.fromarray(arr, "RGB").convert("RGBA")
    return Image.fromarray(arr, "RGBA")


def render_aircraft_pyvista(size=(670, 500)) -> Image.Image:
    plotter, pv = setup_pyvista(size)
    add_soft_lighting(plotter, pv, key=(4.8, -5.8, 4.4), fill=(-4, 2.8, 2.0))

    meshes = [
        make_fuselage(),
        make_swept_wing(1),
        make_swept_wing(-1),
        make_swept_wing(1, root_y=0.18, tip_y=1.18, root_lead=-1.82, root_trail=-2.54, tip_lead=-2.15, tip_trail=-2.90, z_root=0.16, dihedral=0.06, thickness=0.04, nspan=22, nchord=12),
        make_swept_wing(-1, root_y=0.18, tip_y=1.18, root_lead=-1.82, root_trail=-2.54, tip_lead=-2.15, tip_trail=-2.90, z_root=0.16, dihedral=0.06, thickness=0.04, nspan=22, nchord=12),
        make_vertical_tail(),
    ]

    for idx, mesh in enumerate(meshes):
        plotter.add_mesh(
            mesh,
            scalars="Cp",
            cmap="coolwarm",
            clim=(-1.65, 1.05),
            smooth_shading=True,
            ambient=0.38,
            diffuse=0.58,
            specular=0.24,
            specular_power=30,
            show_scalar_bar=idx == 0,
            scalar_bar_args=scalar_bar_args("Cp", pos=(0.86, 0.21), height=0.50) if idx == 0 else None,
        )

    for zoff, alpha, width in ((0.58, 0.30, 1.2), (0.14, 0.20, 0.8), (-0.30, 0.16, 0.7)):
        for y0 in np.linspace(-2.65, 2.65, 5):
            pts = np.column_stack(
                [
                    np.linspace(3.15, -3.05, 130),
                    y0 + 0.13 * np.sin(np.linspace(0, 2.6 * np.pi, 130)),
                    zoff + 0.05 * np.sin(np.linspace(0, 1.4 * np.pi, 130) + y0),
                ]
            )
            plotter.add_mesh(pv.Spline(pts, 130), color="#c9d1d9", opacity=alpha, line_width=width)

    plotter.camera_position = [(5.7, -5.9, 3.25), (0.02, 0.0, 0.07), (0, 0, 1)]
    plotter.camera.zoom(1.08)
    return screenshot_plotter(plotter)


def render_satellite_pyvista(size=(650, 500)) -> Image.Image:
    plotter, pv = setup_pyvista(size)
    add_soft_lighting(plotter, pv, key=(3.2, -4.7, 4.2), fill=(-3.6, 3.2, 2.6))

    parts = [
        make_subdivided_box((0, 0, 0), (1.05, 0.84, 0.76), box_scalar_stress, "vm", density=(17, 13, 13)),
        make_subdivided_box((-1.82, 0, 0), (2.34, 0.055, 0.82), box_scalar_stress, "vm", density=(32, 3, 12)),
        make_subdivided_box((1.82, 0, 0), (2.34, 0.055, 0.82), box_scalar_stress, "vm", density=(32, 3, 12)),
    ]
    for idx, mesh in enumerate(parts):
        plotter.add_mesh(
            mesh,
            scalars="vm",
            cmap="turbo",
            clim=(40, 370),
            smooth_shading=True,
            ambient=0.18,
            diffuse=0.74,
            specular=0.24,
            specular_power=24,
            show_edges=True,
            edge_color="#dbe7ff",
            line_width=0.22,
            show_scalar_bar=idx == 0,
            scalar_bar_args=scalar_bar_args("MPa", pos=(0.855, 0.20), height=0.53) if idx == 0 else None,
        )

    # Panel circuit/grid traces, slightly lifted toward the camera.
    for x0, x1 in ((-2.99, -0.65), (0.65, 2.99)):
        for x in np.linspace(x0 + 0.22, x1 - 0.22, 7):
            plotter.add_mesh(pv.Line((x, -0.052, -0.41), (x, -0.052, 0.41)), color="#e6edf3", opacity=0.34, line_width=0.65)
        for z in np.linspace(-0.28, 0.28, 3):
            plotter.add_mesh(pv.Line((x0 + 0.05, -0.054, z), (x1 - 0.05, -0.054, z)), color="#e6edf3", opacity=0.24, line_width=0.55)

    for x in (-0.72, 0.72):
        rod = pv.Cylinder(center=(x, 0, 0), direction=(1, 0, 0), radius=0.035, height=0.28, resolution=28)
        plotter.add_mesh(rod, color="#c9d1d9", ambient=0.12, diffuse=0.65, specular=0.45, specular_power=35)

    boom_a = pv.Cylinder(center=(0.16, 0.08, 0.80), direction=(0.48, 0.22, 0.78), radius=0.018, height=1.15, resolution=18)
    boom_b = pv.Cylinder(center=(-0.18, -0.05, -0.78), direction=(-0.50, -0.20, -0.75), radius=0.018, height=1.05, resolution=18)
    plotter.add_mesh(boom_a, color="#c9d1d9", opacity=0.86, specular=0.38, specular_power=28)
    plotter.add_mesh(boom_b, color="#c9d1d9", opacity=0.76, specular=0.32, specular_power=24)

    plotter.camera_position = [(4.1, -4.9, 2.9), (0, 0, 0.02), (0, 0, 1)]
    plotter.camera.zoom(1.08)
    return screenshot_plotter(plotter)


def render_truck_pyvista(size=(620, 440)) -> Image.Image:
    plotter, pv = setup_pyvista(size)
    add_soft_lighting(plotter, pv, key=(4.8, -5.2, 4.3), fill=(-3.4, 2.4, 2.3))

    body_parts = [
        make_subdivided_box((-0.55, 0, 0.64), (3.05, 0.92, 1.05), box_scalar_aero, "q", density=(34, 11, 14)),
        make_truck_cab(),
        make_subdivided_box((2.05, 0, 0.38), (0.96, 0.88, 0.64), box_scalar_aero, "q", density=(14, 10, 10)),
    ]
    for idx, mesh in enumerate(body_parts):
        plotter.add_mesh(
            mesh,
            scalars="q",
            cmap="cividis",
            clim=(-0.55, 1.45),
            smooth_shading=True,
            ambient=0.20,
            diffuse=0.72,
            specular=0.36,
            specular_power=34,
            show_scalar_bar=idx == 0,
            scalar_bar_args=scalar_bar_args("q", pos=(0.865, 0.23), height=0.47) if idx == 0 else None,
        )

    for x in (-1.52, -0.18, 1.68):
        for y in (-0.56, 0.56):
            tire = pv.Cylinder(center=(x, y, 0.08), direction=(0, 1, 0), radius=0.255, height=0.15, resolution=56)
            hub = pv.Cylinder(center=(x, y * 1.01, 0.08), direction=(0, 1, 0), radius=0.105, height=0.165, resolution=38)
            plotter.add_mesh(tire, color="#121820", ambient=0.16, diffuse=0.58, specular=0.22, specular_power=18)
            plotter.add_mesh(hub, color="#9fb3c8", ambient=0.18, diffuse=0.62, specular=0.48, specular_power=32)

    ground = pv.Plane(center=(0.28, 0, -0.185), direction=(0, 0, 1), i_size=4.8, j_size=1.9, i_resolution=2, j_resolution=2)
    plotter.add_mesh(ground, color="#17202a", opacity=0.34, ambient=0.42, diffuse=0.42)

    for y in np.linspace(-0.78, 0.78, 4):
        pts = np.column_stack(
            [
                np.linspace(2.88, -2.28, 120),
                y + 0.04 * np.sin(np.linspace(0, 2.1 * np.pi, 120)),
                0.88 + 0.10 * np.sin(np.linspace(0, 1.7 * np.pi, 120) + y),
            ]
        )
        plotter.add_mesh(pv.Spline(pts, 120), color="#c9d1d9", opacity=0.18, line_width=0.75)

    plotter.camera_position = [(4.7, -4.7, 2.6), (0.25, 0, 0.48), (0, 0, 1)]
    plotter.camera.zoom(1.18)
    return screenshot_plotter(plotter)


def render_all_pyvista() -> RenderResult:
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    aircraft = render_aircraft_pyvista()
    satellite = render_satellite_pyvista()
    truck = render_truck_pyvista()
    return RenderResult("pyvista/vtk off-screen", aircraft, satellite, truck)


def mpl_render_to_image(fig: plt.Figure) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, transparent=True, facecolor=(0, 0, 0, 0), edgecolor=(0, 0, 0, 0))
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


def style_mpl_3d(ax) -> None:
    ax.set_facecolor((0, 0, 0, 0))
    ax.set_axis_off()
    ax.xaxis.pane.set_alpha(0)
    ax.yaxis.pane.set_alpha(0)
    ax.zaxis.pane.set_alpha(0)
    ax.grid(False)


def render_aircraft_mpl(size=(670, 500)) -> Image.Image:
    fig = plt.figure(figsize=(size[0] / DPI, size[1] / DPI), dpi=DPI, facecolor=(0, 0, 0, 0))
    ax = fig.add_subplot(111, projection="3d")
    style_mpl_3d(ax)
    xs = np.linspace(-3.05, 3.12, 90)
    th = np.linspace(0, 2 * np.pi, 56)
    xg, tg = np.meshgrid(xs, th)
    s = (xg - xs[0]) / (xs[-1] - xs[0])
    taper = np.maximum(np.sin(np.pi * s) ** 0.43 * (0.76 + 0.24 * np.cos(np.pi * (s - 0.42))), 0.045)
    yg = 0.39 * taper * np.cos(tg)
    zg = 0.46 * taper * np.sin(tg)
    pts = np.column_stack([xg.ravel(), yg.ravel(), zg.ravel()])
    cp = aircraft_cp(pts).reshape(xg.shape)
    norm = Normalize(-1.65, 1.05)
    ax.plot_surface(xg, yg, zg, facecolors=cm.coolwarm(norm(cp)), linewidth=0, antialiased=True, shade=True)
    for side in (-1, 1):
        span = np.linspace(0.3, 2.55, 18)
        chord = np.linspace(0, 1, 12)
        eg, cg = np.meshgrid((span - 0.3) / (2.55 - 0.3), chord)
        y = side * (0.3 + eg * 2.25)
        lead = 0.88 + eg * (-1.26)
        trail = -1.14 + eg * (-1.04)
        x = lead + cg * (trail - lead)
        z = 0.03 + 0.17 * eg + 0.025 * np.sin(np.pi * cg)
        cpw = aircraft_cp(np.column_stack([x.ravel(), y.ravel(), z.ravel()])).reshape(x.shape)
        ax.plot_surface(x, y, z, facecolors=cm.coolwarm(norm(cpw)), linewidth=0.1, antialiased=True, shade=True)
    sm = cm.ScalarMappable(norm=norm, cmap="coolwarm")
    cb = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.0, shrink=0.55)
    cb.set_label("Cp", color=FG, fontsize=8)
    cb.ax.tick_params(colors=FG, labelsize=7, width=0.4)
    ax.view_init(elev=23, azim=-42)
    ax.set_box_aspect((6.2, 5.2, 1.8))
    ax.set_xlim(-3.35, 3.25)
    ax.set_ylim(-2.9, 2.9)
    ax.set_zlim(-0.8, 1.35)
    return mpl_render_to_image(fig)


def render_satellite_mpl(size=(650, 500)) -> Image.Image:
    fig = plt.figure(figsize=(size[0] / DPI, size[1] / DPI), dpi=DPI, facecolor=(0, 0, 0, 0))
    ax = fig.add_subplot(111, projection="3d")
    style_mpl_3d(ax)
    norm = Normalize(40, 370)
    for x0, x1, z0, z1, y in ((-2.99, -0.65, -0.41, 0.41, -0.03), (0.65, 2.99, -0.41, 0.41, -0.03), (-0.52, 0.52, -0.38, 0.38, -0.43)):
        x = np.linspace(x0, x1, 34)
        z = np.linspace(z0, z1, 18)
        xg, zg = np.meshgrid(x, z)
        yg = np.full_like(xg, y)
        stress = box_scalar_stress(np.column_stack([xg.ravel(), yg.ravel(), zg.ravel()])).reshape(xg.shape)
        ax.plot_surface(xg, yg, zg, facecolors=cm.turbo(norm(stress)), linewidth=0.15, edgecolors=(0.86, 0.91, 1.0, 0.22), antialiased=True, shade=True)
    sm = cm.ScalarMappable(norm=norm, cmap="turbo")
    cb = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.0, shrink=0.58)
    cb.set_label("MPa", color=FG, fontsize=8)
    cb.ax.tick_params(colors=FG, labelsize=7, width=0.4)
    ax.view_init(elev=24, azim=-44)
    ax.set_box_aspect((6, 2.2, 1.7))
    ax.set_xlim(-3.2, 3.2)
    ax.set_ylim(-1.0, 1.0)
    ax.set_zlim(-1.0, 1.2)
    return mpl_render_to_image(fig)


def render_truck_mpl(size=(620, 440)) -> Image.Image:
    fig = plt.figure(figsize=(size[0] / DPI, size[1] / DPI), dpi=DPI, facecolor=(0, 0, 0, 0))
    ax = fig.add_subplot(111, projection="3d")
    style_mpl_3d(ax)
    norm = Normalize(-0.55, 1.45)
    for center, box_size in (((-0.55, 0, 0.64), (3.05, 0.92, 1.05)), ((2.0, 0, 0.48), (1.05, 0.88, 0.78))):
        cx, cy, cz = center
        sx, sy, sz = box_size
        x = np.linspace(cx - sx / 2, cx + sx / 2, 28)
        z = np.linspace(cz - sz / 2, cz + sz / 2, 12)
        xg, zg = np.meshgrid(x, z)
        for y in (cy - sy / 2, cy + sy / 2):
            yg = np.full_like(xg, y)
            q = box_scalar_aero(np.column_stack([xg.ravel(), yg.ravel(), zg.ravel()])).reshape(xg.shape)
            ax.plot_surface(xg, yg, zg, facecolors=cm.cividis(norm(q)), linewidth=0, antialiased=True, shade=True)
    for x in (-1.52, -0.18, 1.68):
        th = np.linspace(0, 2 * np.pi, 32)
        y = np.linspace(-0.63, -0.48, 4)
        tg, yg = np.meshgrid(th, y)
        ax.plot_surface(np.full_like(tg, x), yg, 0.08 + 0.255 * np.sin(tg), color="#121820", linewidth=0, shade=True)
    sm = cm.ScalarMappable(norm=norm, cmap="cividis")
    cb = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.0, shrink=0.50)
    cb.set_label("q", color=FG, fontsize=8)
    cb.ax.tick_params(colors=FG, labelsize=7, width=0.4)
    ax.view_init(elev=23, azim=-42)
    ax.set_box_aspect((5.6, 2.2, 1.8))
    ax.set_xlim(-2.4, 2.8)
    ax.set_ylim(-1.2, 1.0)
    ax.set_zlim(-0.3, 1.45)
    return mpl_render_to_image(fig)


def render_all_matplotlib() -> RenderResult:
    return RenderResult(
        "matplotlib 3d fallback",
        render_aircraft_mpl(),
        render_satellite_mpl(),
        render_truck_mpl(),
    )


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


def draw_text_layer(image: Image.Image, renderer: str) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = load_font(44, "bold")
    subtitle_font = load_font(15, "regular")
    label_font = load_font(13, "regular")
    small_font = load_font(11, "regular")
    wordmark_font = load_font(15, "regular")

    draw.text((92, 72), "Agentic Digital Twins, as Code", fill=hex_to_rgba(INK, 242), font=title_font)
    draw.text((94, 124), "claude code plugin", fill=hex_to_rgba(MUTED, 206), font=subtitle_font)
    draw.line((94, 154, 315, 154), fill=hex_to_rgba(ACCENT, 120), width=1)

    labels = [
        ((116, 558), "cfd", "surface pressure"),
        ((610, 558), "fea", "von-mises stress"),
        ((1116, 558), "telemetry", "aero response"),
    ]
    for (x, y), main, detail in labels:
        draw.text((x, y), main, fill=hex_to_rgba(INK, 224), font=label_font)
        draw.text((x, y + 20), detail, fill=hex_to_rgba(MUTED, 176), font=small_font)

    draw.text((92, 736), "agentic-digital-twin", fill=hex_to_rgba(MUTED, 214), font=wordmark_font)
    draw.line((92, 729, 231, 729), fill=hex_to_rgba(GRID, 90), width=1)


def composite(rendered: RenderResult) -> Image.Image:
    canvas = make_background()
    add_background_lines(canvas)
    draw = ImageDraw.Draw(canvas, "RGBA")

    aircraft = resize_render(rendered.aircraft, (610, 455))
    satellite = resize_render(rendered.satellite, (595, 455))
    truck = resize_render(rendered.truck, (520, 370))
    charts = render_charts((520, 136))

    paste_with_shadow(canvas, aircraft, (35, 164))
    paste_with_shadow(canvas, satellite, (500, 154))
    paste_with_shadow(canvas, truck, (1016, 218))

    chart_panel = Image.new("RGBA", (552, 166), (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(chart_panel, "RGBA")
    panel_draw.rounded_rectangle((0, 0, 551, 165), radius=8, fill=(9, 13, 19, 172), outline=hex_to_rgba(GRID, 122), width=1)
    chart_panel.alpha_composite(charts, (16, 15))
    canvas.alpha_composite(chart_panel, (952, 590))

    draw.line((92, 620, 854, 620), fill=hex_to_rgba(GRID, 34), width=1)
    draw_text_layer(canvas, rendered.renderer)
    return canvas


def render() -> RenderResult:
    try:
        return render_all_pyvista()
    except Exception:
        traceback.print_exc()
        return render_all_matplotlib()


def main() -> None:
    out = Path(__file__).resolve().with_name("hero.png")
    rendered = render()
    image = composite(rendered)
    image = image.convert("RGB")
    image.save(out, "PNG", optimize=True)
    width, height = png_size(out)
    print(f"renderer: {rendered.renderer}")
    print(f"wrote {out} ({width}x{height}px)")


if __name__ == "__main__":
    main()
