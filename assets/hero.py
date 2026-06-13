# /// script
# dependencies = [
#   "matplotlib",
#   "numpy",
# ]
# ///

from __future__ import annotations

from pathlib import Path
import struct

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np
from matplotlib.patches import Circle, Polygon, Rectangle


WIDTH = 1600
HEIGHT = 800
DPI = 100

BG = "#0d1117"
FG = "#c9d1d9"
MUTED = "#8b949e"
GRID = "#30363d"
INK = "#e6edf3"
CMAP = "turbo"

MARGIN_X = 96
GUTTER_X = 56
COL_W = (WIDTH - 2 * MARGIN_X - 2 * GUTTER_X) / 3
COL_X = [MARGIN_X + i * (COL_W + GUTTER_X) for i in range(3)]
COL_CX = [x + COL_W / 2 for x in COL_X]
PANEL_Y = 260
PANEL_H = 230
PANEL_TOP = PANEL_Y + PANEL_H
SUBJECT_CY = 620


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        header = fh.read(24)
    return struct.unpack(">II", header[16:24])


def style_field_axis(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def style_chart_axis(ax: plt.Axes) -> None:
    ax.set_facecolor((0, 0, 0, 0))
    ax.tick_params(axis="both", colors=MUTED, labelsize=5, width=0.35, length=2, pad=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(0.45)
    ax.grid(True, which="major", axis="y", color=GRID, linewidth=0.35, alpha=0.24)


def transform(points: np.ndarray, center: tuple[float, float], scale: float) -> np.ndarray:
    pts = np.asarray(points, dtype=float).copy()
    pts *= scale
    pts[:, 0] += center[0]
    pts[:, 1] += center[1]
    return pts


def fig_rect(x: float, y: float, width: float, height: float) -> list[float]:
    return [x / WIDTH, y / HEIGHT, width / WIDTH, height / HEIGHT]


def draw_aircraft(canvas: plt.Axes, center: tuple[float, float], scale: float) -> None:
    fuselage = np.array(
        [
            [-218, 0],
            [-184, 18],
            [112, 19],
            [174, 12],
            [216, 0],
            [174, -12],
            [112, -19],
            [-184, -18],
        ]
    )
    wing_top = np.array([[0, 12], [-84, 112], [-24, 112], [62, 17]])
    wing_bottom = wing_top * np.array([1, -1])
    tail_top = np.array([[-158, 12], [-214, 58], [-162, 54], [-112, 12]])
    tail_bottom = tail_top * np.array([1, -1])
    vertical_tail = np.array([[-174, 14], [-126, 82], [-92, 16]])
    cockpit = np.array([[112, 18], [143, 12], [161, 4]])
    centerline = np.array([[-176, 0], [176, 0]])

    for poly in (wing_top, wing_bottom, tail_top, tail_bottom, vertical_tail, fuselage):
        canvas.add_patch(
            Polygon(
                transform(poly, center, scale),
                closed=True,
                fill=False,
                edgecolor=FG,
                linewidth=0.85,
                alpha=0.78,
                joinstyle="round",
            )
        )
    for line in (cockpit, centerline):
        pts = transform(line, center, scale)
        canvas.plot(pts[:, 0], pts[:, 1], color=FG, linewidth=0.55, alpha=0.48)


def draw_satellite(canvas: plt.Axes, center: tuple[float, float], scale: float) -> None:
    panels = [
        np.array([[-230, -42], [-62, -42], [-62, 42], [-230, 42]]),
        np.array([[62, -42], [230, -42], [230, 42], [62, 42]]),
    ]
    bus = np.array([[-58, -62], [58, -62], [58, 62], [-58, 62]])
    mast_top = np.array([[18, 62], [68, 98], [116, 118]])
    mast_bottom = np.array([[-18, -62], [-74, -98], [-122, -118]])

    for poly in (*panels, bus):
        canvas.add_patch(
            Polygon(
                transform(poly, center, scale),
                closed=True,
                fill=False,
                edgecolor=FG,
                linewidth=0.82,
                alpha=0.78,
                joinstyle="round",
            )
        )

    for x in (-196, -162, -128, -94, 94, 128, 162, 196):
        pts = transform(np.array([[x, -42], [x, 42]]), center, scale)
        canvas.plot(pts[:, 0], pts[:, 1], color=FG, linewidth=0.36, alpha=0.34)
    for y in (-14, 14):
        for x0, x1 in ((-230, -62), (62, 230)):
            pts = transform(np.array([[x0, y], [x1, y]]), center, scale)
            canvas.plot(pts[:, 0], pts[:, 1], color=FG, linewidth=0.34, alpha=0.30)

    for line in (mast_top, mast_bottom):
        pts = transform(line, center, scale)
        canvas.plot(pts[:, 0], pts[:, 1], color=FG, linewidth=0.55, alpha=0.52)
    for x, y in ((116, 118), (-122, -118)):
        cx, cy = transform(np.array([[x, y]]), center, scale)[0]
        canvas.add_patch(Circle((cx, cy), 5.8 * scale, fill=False, edgecolor=FG, linewidth=0.5, alpha=0.46))


def draw_truck(canvas: plt.Axes, center: tuple[float, float], scale: float) -> None:
    body = np.array(
        [
            [-210, -34],
            [-210, 20],
            [-88, 20],
            [-60, 52],
            [26, 52],
            [62, 20],
            [168, 20],
            [194, 5],
            [210, 5],
            [210, -34],
            [-210, -34],
        ]
    )
    cab_window = np.array([[-50, 40], [18, 40], [42, 20], [-68, 20]])
    bed_line = np.array([[70, 20], [70, -34]])
    chassis = np.array([[-210, -34], [210, -34]])

    canvas.add_patch(
        Polygon(
            transform(body, center, scale),
            closed=True,
            fill=False,
            edgecolor=FG,
            linewidth=0.9,
            alpha=0.82,
            joinstyle="round",
        )
    )
    canvas.add_patch(
        Polygon(
            transform(cab_window, center, scale),
            closed=True,
            fill=False,
            edgecolor=FG,
            linewidth=0.65,
            alpha=0.58,
            joinstyle="round",
        )
    )
    for line in (bed_line, chassis):
        pts = transform(line, center, scale)
        canvas.plot(pts[:, 0], pts[:, 1], color=FG, linewidth=0.65, alpha=0.55)

    for x in (-122, 125):
        cx, cy = transform(np.array([[x, -35]]), center, scale)[0]
        canvas.add_patch(Circle((cx, cy), 24 * scale, fill=False, edgecolor=FG, linewidth=0.85, alpha=0.74))
        canvas.add_patch(Circle((cx, cy), 8 * scale, fill=False, edgecolor=FG, linewidth=0.55, alpha=0.45))


def airfoil_points(n: int = 240) -> tuple[np.ndarray, np.ndarray]:
    s = np.linspace(0.001, 1.0, n)
    thickness = 0.12
    yt = 5 * thickness * (
        0.2969 * np.sqrt(s)
        - 0.1260 * s
        - 0.3516 * s**2
        + 0.2843 * s**3
        - 0.1015 * s**4
    )
    camber = 0.045 * np.sin(np.pi * s)
    dyc = 0.045 * np.pi * np.cos(np.pi * s)
    theta = np.arctan(dyc)

    xu = s - yt * np.sin(theta)
    yu = camber + yt * np.cos(theta)
    xl = s + yt * np.sin(theta)
    yl = camber - yt * np.cos(theta)

    x = -1.43 + 2.86 * np.r_[xu, xl[::-1]]
    y = 0.92 * (np.r_[yu, yl[::-1]] - 0.015)
    return x, y


def render_cfd(ax: plt.Axes) -> None:
    x = np.linspace(-2.45, 2.55, 360)
    y = np.linspace(-1.25, 1.25, 240)
    xg, yg = np.meshgrid(x, y)

    suction = -1.55 * np.exp(-((xg + 0.22) / 0.98) ** 2 - ((yg - 0.23) / 0.24) ** 2)
    pressure = 1.05 * np.exp(-((xg + 0.08) / 0.88) ** 2 - ((yg + 0.19) / 0.28) ** 2)
    wake = 0.42 * np.exp(-((xg - 1.0) / 1.30) ** 2 - (yg / 0.42) ** 2) * np.cos(2.7 * yg)
    leading = -0.48 * np.exp(-((xg + 1.08) / 0.30) ** 2 - (yg / 0.43) ** 2)
    field = suction + pressure + wake + leading + 0.12 * yg

    levels = np.linspace(float(field.min()), float(field.max()), 28)
    ax.contourf(xg, yg, field, levels=levels, cmap=CMAP, alpha=0.78, antialiased=True)

    u = 1.0
    u += 0.45 * np.exp(-((xg + 0.25) / 0.95) ** 2 - ((yg - 0.24) / 0.26) ** 2)
    u -= 0.26 * np.exp(-((xg + 0.02) / 0.86) ** 2 - ((yg + 0.17) / 0.27) ** 2)
    v = 0.13 * np.sin(1.3 * xg) * np.exp(-(yg / 0.85) ** 2)
    v -= 0.24 * yg * np.exp(-((xg + 0.2) / 1.05) ** 2 - (yg / 0.48) ** 2)
    ax.streamplot(
        x,
        y,
        u,
        v,
        density=(1.05, 0.62),
        color=(0.90, 0.93, 0.97, 0.38),
        linewidth=0.42,
        arrowsize=0.45,
        minlength=0.15,
    )

    af_x, af_y = airfoil_points()
    ax.add_patch(
        Polygon(
            np.column_stack([af_x, af_y]),
            closed=True,
            facecolor=BG,
            edgecolor=INK,
            linewidth=0.85,
            alpha=0.94,
            zorder=6,
            joinstyle="round",
        )
    )
    ax.plot([-1.26, 1.22], [0.006, 0.03], color=FG, linewidth=0.45, alpha=0.42, zorder=7)
    ax.set_xlim(-2.45, 2.55)
    ax.set_ylim(-1.25, 1.25)


def inside_satellite(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    left_panel = (-2.35 <= x) & (x <= -0.55) & (-0.48 <= y) & (y <= 0.48)
    bus = (-0.65 <= x) & (x <= 0.65) & (-0.70 <= y) & (y <= 0.70)
    right_panel = (0.55 <= x) & (x <= 2.35) & (-0.48 <= y) & (y <= 0.48)
    return left_panel | bus | right_panel


def rect_boundary(x0: float, x1: float, y0: float, y1: float, nx: int, ny: int) -> np.ndarray:
    top = np.column_stack([np.linspace(x0, x1, nx), np.full(nx, y1)])
    bottom = np.column_stack([np.linspace(x0, x1, nx), np.full(nx, y0)])
    left = np.column_stack([np.full(ny, x0), np.linspace(y0, y1, ny)])
    right = np.column_stack([np.full(ny, x1), np.linspace(y0, y1, ny)])
    return np.vstack([top, bottom, left, right])


def triangular_lattice(x0: float, x1: float, y0: float, y1: float, step: float) -> np.ndarray:
    rows = []
    dy = step * np.sqrt(3) / 2
    for row, y in enumerate(np.arange(y0, y1 + dy, dy)):
        offset = 0.5 * step if row % 2 else 0.0
        xs = np.arange(x0, x1 + step, step) + offset
        rows.append(np.column_stack([xs, np.full_like(xs, y)]))
    return np.vstack(rows)


def unique_points(points: np.ndarray) -> np.ndarray:
    return np.unique(np.round(points, 5), axis=0)


def render_fea(ax: plt.Axes) -> None:
    step = 0.135
    raw = triangular_lattice(-2.35, 2.35, -0.70, 0.70, step)
    raw = raw[inside_satellite(raw[:, 0], raw[:, 1])]

    boundaries = np.vstack(
        [
            rect_boundary(-2.35, -0.55, -0.48, 0.48, 34, 18),
            rect_boundary(-0.65, 0.65, -0.70, 0.70, 26, 24),
            rect_boundary(0.55, 2.35, -0.48, 0.48, 34, 18),
        ]
    )
    pts = unique_points(np.vstack([raw, boundaries]))

    tri = mtri.Triangulation(pts[:, 0], pts[:, 1])
    centers_x = pts[tri.triangles].mean(axis=1)[:, 0]
    centers_y = pts[tri.triangles].mean(axis=1)[:, 1]
    mask = ~inside_satellite(centers_x, centers_y)

    edges = pts[tri.triangles][:, [0, 1, 2, 0], :]
    edge_lengths = np.sqrt(np.sum(np.diff(edges, axis=1) ** 2, axis=2))
    mask |= np.max(edge_lengths, axis=1) > 0.30
    tri.set_mask(mask)

    x, y = pts[:, 0], pts[:, 1]
    stress = 0.16 + 0.10 * (np.abs(x) / 2.35) + 0.16 * (np.abs(y) / 0.70)
    stress += 1.35 * np.exp(-((x + 0.58) / 0.22) ** 2 - (y / 0.50) ** 2)
    stress += 1.35 * np.exp(-((x - 0.58) / 0.22) ** 2 - (y / 0.50) ** 2)
    stress += 0.58 * np.exp(-((x - 1.62) / 0.58) ** 2 - ((y - 0.27) / 0.30) ** 2)
    stress += 0.42 * np.exp(-((x + 1.45) / 0.70) ** 2 - ((y + 0.22) / 0.34) ** 2)
    stress = (stress - stress.min()) / (stress.max() - stress.min())

    ax.tripcolor(tri, stress, cmap=CMAP, shading="gouraud", alpha=0.88, zorder=1)
    ax.triplot(tri, color=(0.90, 0.93, 0.97, 0.24), linewidth=0.30, zorder=2)

    outlines = [
        (-2.35, -0.48, 1.80, 0.96),
        (-0.65, -0.70, 1.30, 1.40),
        (0.55, -0.48, 1.80, 0.96),
    ]
    for x0, y0, width, height in outlines:
        ax.add_patch(
            Rectangle(
                (x0, y0),
                width,
                height,
                fill=False,
                edgecolor=INK,
                linewidth=0.82,
                alpha=0.76,
                zorder=5,
            )
        )

    for x_cell in np.linspace(-2.05, -0.85, 5):
        ax.plot([x_cell, x_cell], [-0.48, 0.48], color=FG, linewidth=0.34, alpha=0.38, zorder=6)
    for x_cell in np.linspace(0.85, 2.05, 5):
        ax.plot([x_cell, x_cell], [-0.48, 0.48], color=FG, linewidth=0.34, alpha=0.38, zorder=6)
    ax.plot([-0.10, 0.42, 0.66], [0.72, 1.03, 1.14], color=FG, linewidth=0.55, alpha=0.55, zorder=6)
    ax.plot([0.10, -0.44, -0.72], [-0.72, -1.02, -1.12], color=FG, linewidth=0.55, alpha=0.55, zorder=6)
    ax.set_xlim(-2.55, 2.55)
    ax.set_ylim(-1.30, 1.30)
    ax.set_aspect("equal", adjustable="box")


def render_residual(ax: plt.Axes, cmap) -> None:
    iterations = np.arange(1, 86)
    residual = np.exp(-iterations / 12.5) * (1 + 0.12 * np.sin(iterations * 0.42)) + 1.6e-4
    ax.semilogy(iterations, residual, color=cmap(0.17), linewidth=1.35)
    ax.set_xlim(1, 85)
    ax.set_ylim(1e-4, 1.0)
    ax.set_xticks([1, 40, 80])
    ax.set_yticks([1e-4, 1e-2, 1])
    ax.set_yticklabels(["1e-4", "1e-2", "1"])
    ax.text(0.04, 0.86, "residual", transform=ax.transAxes, color=MUTED, fontsize=5.8)


def render_history(ax: plt.Axes, cmap) -> None:
    t = np.linspace(0, 10, 220)
    load = 0.50 + 0.28 * np.sin(1.35 * t) + 0.18 * ((t > 3.5) & (t < 6.8))
    response = 0.47 + 0.22 * np.sin(1.35 * t - 0.58) + 0.15 * (1 - np.exp(-0.8 * np.maximum(t - 3.5, 0)))
    response -= 0.13 * (1 - np.exp(-1.2 * np.maximum(t - 6.8, 0)))
    ax.plot(t, load, color=cmap(0.68), linewidth=1.15)
    ax.plot(t, response, color=cmap(0.33), linewidth=1.15)
    ax.set_xlim(0, 10)
    ax.set_ylim(0.05, 1.05)
    ax.set_xticks([0, 5, 10])
    ax.set_yticks([0.2, 0.8])
    ax.text(0.04, 0.86, "load", transform=ax.transAxes, color=cmap(0.68), fontsize=5.8)
    ax.text(0.33, 0.86, "resp", transform=ax.transAxes, color=cmap(0.33), fontsize=5.8)


def main() -> None:
    out = Path(__file__).resolve().with_name("hero.png")
    cmap = plt.get_cmap(CMAP)

    fig = plt.figure(figsize=(WIDTH / DPI, HEIGHT / DPI), dpi=DPI, facecolor=BG)
    canvas = fig.add_axes([0, 0, 1, 1], facecolor=BG)
    canvas.set_xlim(0, WIDTH)
    canvas.set_ylim(0, HEIGHT)
    canvas.axis("off")

    canvas.plot([MARGIN_X, WIDTH - MARGIN_X], [198, 198], color=GRID, linewidth=0.5, alpha=0.22)

    draw_aircraft(canvas, center=(COL_CX[0], SUBJECT_CY), scale=0.66)
    draw_satellite(canvas, center=(COL_CX[1], SUBJECT_CY), scale=0.72)
    draw_truck(canvas, center=(COL_CX[2], SUBJECT_CY - 6), scale=0.86)

    cfd_ax = fig.add_axes(fig_rect(COL_X[0], PANEL_Y, COL_W, PANEL_H))
    style_field_axis(cfd_ax)
    render_cfd(cfd_ax)

    fea_ax = fig.add_axes(fig_rect(COL_X[1], PANEL_Y, COL_W, PANEL_H))
    style_field_axis(fea_ax)
    render_fea(fea_ax)

    chart_gap = 22
    chart_w = (COL_W - chart_gap) / 2
    residual_ax = fig.add_axes(fig_rect(COL_X[2], PANEL_Y, chart_w, PANEL_H))
    history_ax = fig.add_axes(fig_rect(COL_X[2] + chart_w + chart_gap, PANEL_Y, chart_w, PANEL_H))
    for chart_ax in (residual_ax, history_ax):
        style_chart_axis(chart_ax)
    render_residual(residual_ax, cmap)
    render_history(history_ax, cmap)

    label_style = dict(color=MUTED, fontsize=8, family="DejaVu Sans", alpha=0.90)
    for x, label in zip(COL_X, ("cfd", "fea", "telemetry")):
        canvas.text(x + 2, PANEL_TOP + 18, label, **label_style)

    canvas.text(
        MARGIN_X,
        58,
        "agentic-digital-twin",
        color=MUTED,
        fontsize=10.5,
        family="DejaVu Sans",
        alpha=0.82,
    )
    canvas.plot([MARGIN_X, MARGIN_X + 120], [49, 49], color=GRID, linewidth=0.55, alpha=0.35)

    fig.savefig(out, dpi=DPI, facecolor=BG, edgecolor=BG)
    plt.close(fig)

    width, height = png_size(out)
    print(f"wrote {out} ({width}x{height}px)")


if __name__ == "__main__":
    main()
