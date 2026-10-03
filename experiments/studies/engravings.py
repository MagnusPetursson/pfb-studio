"""Field engravings: stable expression grammars revealed through level sets.

This study inherits PFB's seeded function composition, rather than its particle
renderer. See src/legacy/variations.h (createFieldTree2) and perlin.cpp.
Mathematical/artistic antecedent: GenerateMe, Drawing vector field (2016),
https://generateme.wordpress.com/2016/04/24/drawing-vector-field/ .
Expressions contain no per-evaluation randomness. Scouting and final sampling
evaluate the same continuous function; all expression parameters are recorded.
"""

from __future__ import annotations

import math
from typing import Any

import aggdraw
import contourpy
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

TITLE = "Field Engravings"
DESCRIPTION = "Seeded equations etched as fine bands, folds, and nested contours on paper."
CONTROLS = {
    "fold_scale": {"default": 0.5, "label": "Fold scale"},
    "level_spacing": {"default": 0.5, "label": "Level spacing"},
    "directional_bias": {"default": 0.5, "label": "Directional bias"},
    "mark_density": {"default": 0.5, "label": "Mark density"},
}


def _settings(controls: dict | None) -> dict[str, float]:
    out = {name: float(spec["default"]) for name, spec in CONTROLS.items()}
    for name, value in (controls or {}).items():
        if name not in out:
            continue
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be finite and in [0, 1]")
        out[name] = value
    return out


def _leaf(rng: np.random.Generator) -> dict[str, Any]:
    return {
        "op": str(rng.choice(["ridge", "saddle", "basin", "waves", "crease"])),
        "angle": float(rng.uniform(-math.pi, math.pi)),
        "center": rng.uniform(-0.9, 0.9, 2).tolist(),
        "scale": rng.uniform(0.55, 1.65, 2).tolist(),
        "phase": float(rng.uniform(-math.pi, math.pi)),
        "frequency": float(rng.uniform(1.1, 3.8)),
    }


def _tree(rng: np.random.Generator, depth: int) -> dict[str, Any]:
    if depth == 0 or rng.random() < 0.25:
        return _leaf(rng)
    op = str(rng.choice(["add", "product", "fold", "warp"], p=[0.35, 0.16, 0.20, 0.29]))
    node: dict[str, Any] = {"op": op, "a": _tree(rng, depth - 1)}
    if op in ("add", "product"):
        node["b"] = _tree(rng, depth - 1)
        node["weight"] = float(rng.uniform(0.25, 0.75))
    elif op == "fold":
        node["frequency"] = float(rng.uniform(0.8, 2.6))
        node["phase"] = float(rng.uniform(-1, 1))
    else:
        node["amount"] = float(rng.uniform(0.15, 0.65))
        node["frequency"] = float(rng.uniform(0.9, 2.4))
        node["phase"] = float(rng.uniform(-math.pi, math.pi))
    return node


def evaluate(node: dict[str, Any], x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Evaluate a saved expression without consuming or consulting an RNG."""
    op = node["op"]
    if op == "add":
        w = node["weight"]
        return w * evaluate(node["a"], x, y) + (1 - w) * evaluate(node["b"], x, y)
    if op == "product":
        return np.tanh(evaluate(node["a"], x, y)) * evaluate(node["b"], x, y)
    if op == "fold":
        v = evaluate(node["a"], x, y)
        return 0.25 * v + np.sin(node["frequency"] * v + node["phase"])
    if op == "warp":
        a, f, p = node["amount"], node["frequency"], node["phase"]
        return evaluate(node["a"], x + a * np.sin(f * y + p), y + a * np.cos(f * x - p))
    c, s = math.cos(node["angle"]), math.sin(node["angle"])
    xx, yy = x - node["center"][0], y - node["center"][1]
    u = (xx * c - yy * s) * node["scale"][0]
    v = (xx * s + yy * c) * node["scale"][1]
    f, p = node["frequency"], node["phase"]
    if op == "ridge":
        return u + 0.5 * np.sin(f * v + p) + 0.12 * v * v
    if op == "saddle":
        return 0.6 * (u * u - v * v) + 0.35 * np.sin(f * u * v + p)
    if op == "basin":
        return np.sqrt(0.035 + u * u + v * v) + 0.3 * np.sin(f * u + p) * np.cos(1.3 * v)
    if op == "waves":
        return np.sin(f * u + p) + 0.6 * np.cos((f * 0.71) * v - p) + 0.22 * u
    if op == "crease":
        return np.arctan((u + 0.45 * np.sin(v * f)) * 2.5) + 0.35 * v
    raise ValueError(f"Unknown expression operation {op!r}")


def _paper(width: int, height: int, color: np.ndarray, rng: np.random.Generator) -> Image.Image:
    # The material RNG is separate from the expression RNG: changing resolution
    # never changes the generated mathematical program.
    grain = rng.normal(0, 0.72, (height, width)).astype(np.float32)
    fiber = gaussian_filter(rng.normal(0, 1, (height, width)).astype(np.float32), (0.5, 7))
    pixels = np.clip(color[None, None, :] + (grain + fiber * 1.4)[..., None], 0, 255)
    return Image.fromarray(pixels.astype(np.uint8))


def render(seed: int, width: int, height: int, controls: dict | None = None) -> tuple[Image.Image, dict]:
    if width < 64 or height < 64:
        raise ValueError("Images must be at least 64 pixels on each side")
    cfg = _settings(controls)
    rng = np.random.default_rng(int(seed))
    material_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 73013]))
    aspect = width / height
    extent_x, extent_y = 1.65 * math.sqrt(aspect), 1.65 / math.sqrt(aspect)
    domain_scale = 0.75 + cfg["fold_scale"] * 1.2
    bias_angle = float(rng.uniform(-math.pi, math.pi))
    bias_amount = (cfg["directional_bias"] - 0.5) * 1.25
    # Select one expression for the seed at neutral controls and square aspect.
    # Slider changes and output framing then evaluate that saved expression.
    scout_x, scout_y = np.meshgrid(np.linspace(-1.65, 1.65, 112), np.linspace(-1.65, 1.65, 112))
    scout_scale = 0.75 + float(CONTROLS["fold_scale"]["default"]) * 1.2
    candidates = []
    # Selection rejects flat/overly oscillatory functions. It does not select a
    # winning image or seed, and uses the same bounded rule for every seed.
    for index in range(5):
        node = _tree(rng, int(rng.integers(2, 4)))
        values = evaluate(node, scout_x * scout_scale, scout_y * scout_scale)
        lo, hi = np.quantile(values, [0.035, 0.965])
        spread = float(hi - lo)
        if not np.isfinite(values).all() or spread < 1e-5:
            candidates.append((-1.0, index, node, float(lo), float(hi)))
            continue
        z = (values - lo) / spread
        gy, gx = np.gradient(z)
        roughness = float(np.mean(np.hypot(gx, gy)))
        occupancy = float(np.mean((z > 0.25) & (z < 0.75)))
        score = 1.0 - abs(occupancy - 0.50) - abs(roughness - 0.022) * 4
        candidates.append((score, index, node, float(lo), float(hi)))
    winner = max(candidates, key=lambda item: item[0])
    _, chosen, node, lo, hi = winner
    frame_x, frame_y = np.meshgrid(np.linspace(-extent_x, extent_x, 112), np.linspace(-extent_y, extent_y, 112))
    frame_values = evaluate(node, frame_x * domain_scale, frame_y * domain_scale)
    lo, hi = (float(v) for v in np.quantile(frame_values, [0.035, 0.965]))
    hi = max(hi, lo + 1e-5)
    grid_w = max(192, min(840, round(width * 0.76)))
    grid_h = max(192, min(840, round(height * 0.76)))
    xs = np.linspace(-extent_x, extent_x, grid_w)
    ys = np.linspace(-extent_y, extent_y, grid_h)
    xx, yy = np.meshgrid(xs, ys)
    values = evaluate(node, xx * domain_scale, yy * domain_scale)
    values = (values - lo) / (hi - lo)
    values += bias_amount * (xx * math.cos(bias_angle) + yy * math.sin(bias_angle))
    # A sub-grid low-pass prevents unstable tiny contours at the raster limit.
    values = gaussian_filter(values, 0.42)
    palettes = [
        ([241, 235, 220], [27, 50, 61], [157, 65, 43]),
        ([239, 233, 216], [45, 51, 42], [170, 117, 49]),
        ([232, 233, 225], [37, 57, 73], [169, 75, 58]),
        ([238, 226, 211], [72, 40, 41], [34, 90, 101]),
        ([234, 232, 222], [43, 53, 61], [131, 103, 148]),
    ]
    palette_index = int(rng.integers(len(palettes)))
    paper, ink, accent = [np.asarray(c, dtype=np.float64) for c in palettes[palette_index]]
    image = _paper(width, height, paper, material_rng)
    draw = aggdraw.Draw(image)
    generator = contourpy.contour_generator(x=xs, y=ys, z=values, name="serial")
    margin = min(width, height) * 0.038
    scale_x, scale_y = (width - 2 * margin) / (2 * extent_x), (height - 2 * margin) / (2 * extent_y)
    line_scale = min(width, height) / 1024
    spacing = 0.0045 + cfg["level_spacing"] * 0.012
    band_count = int(rng.integers(2, 5))
    centers = np.sort(rng.uniform(0.08, 0.92, band_count))
    spans = rng.uniform(0.065, 0.145, band_count)
    level_count, path_count = 0, 0
    for level in np.arange(-0.16, 1.18, spacing):
        distances = np.abs(centers - level) / spans
        band = int(np.argmin(distances))
        distance = float(distances[band])
        # Weak guide contours remain between richer bands; the paper stays open.
        if distance > 1.0:
            if level_count % 5:
                level_count += 1
                continue
            strength = 0.09
            color = ink
        else:
            strength = 0.65 + 0.25 * (1 - distance)
            color = accent if band == band_count - 1 and band_count > 2 else ink
        mixed = tuple(np.clip(paper * (1 - strength) + color * strength, 0, 255).astype(int))
        pen = aggdraw.Pen(mixed, max(0.35, (0.58 + 0.32 * (1 - min(1, distance))) * line_scale))
        for line in generator.lines(float(level)):
            if len(line) < 6:
                continue
            px = margin + (line[:, 0] + extent_x) * scale_x
            py = margin + (line[:, 1] + extent_y) * scale_y
            path = aggdraw.Path()
            path.moveto(float(px[0]), float(py[0]))
            for x, y in zip(px[1:], py[1:]):
                path.lineto(float(x), float(y))
            draw.path(path, None, pen)
            path_count += 1
        level_count += 1
    draw.flush()
    # Sparse hatching follows the field gradient, concentrated near a seam.
    gy, gx = np.gradient(values)
    hatch_draw = aggdraw.Draw(image)
    hatch_count = 0
    mark_count = int(1800 * cfg["mark_density"])
    mark_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 83017]))
    for ix, iy in zip(mark_rng.integers(2, grid_w - 2, mark_count), mark_rng.integers(2, grid_h - 2, mark_count)):
        dist = float(np.min(np.abs(centers - values[iy, ix]) / spans))
        if not 0.85 < dist < 1.2:
            continue
        direction = np.array([gx[iy, ix], gy[iy, ix]])
        length = float(np.linalg.norm(direction))
        if length < 1e-8:
            continue
        direction *= (2.0 + min(5.0, length * 150)) * line_scale / length
        x = margin + ix / (grid_w - 1) * (width - 2 * margin)
        y = margin + iy / (grid_h - 1) * (height - 2 * margin)
        path = aggdraw.Path()
        path.moveto(x, y)
        path.lineto(x + float(direction[0]), y + float(direction[1]))
        hatch_draw.path(path, None, aggdraw.Pen(tuple((paper * 0.45 + ink * 0.55).astype(int)), max(0.35, 0.6 * line_scale)))
        hatch_count += 1
    hatch_draw.flush()
    return image, {
        "algorithm": "stable scalar expression grammar / contour engraving",
        "seed": int(seed), "width": width, "height": height, "controls": cfg,
        "expression": node, "candidate_count": len(candidates), "selected_candidate": chosen,
        "candidate_scores": [float(c[0]) for c in candidates],
        "selection_controls": _settings(None), "selection_aspect": 1.0,
        "normalization": [lo, hi], "domain_scale": domain_scale,
        "directional_angle": bias_angle, "band_centers": centers.tolist(),
        "band_half_widths": spans.tolist(), "palette_index": palette_index,
        "sampling_grid": [grid_w, grid_h], "sample_count": grid_w * grid_h,
        "contour_levels_considered": level_count, "contour_paths": path_count,
        "hatch_marks": hatch_count, "evaluation_randomness": "none",
    }
