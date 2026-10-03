"""Related attractor families with persistent, seeded transform transitions.

Inspired by PFB's src/legacy/fractal.cpp: a shared nonlinear vocabulary,
weighted transform mixtures, orbit-dependent color and layered accumulation.
Original mathematics: Scott Draves and Erik Reckase, The Fractal Flame
Algorithm, https://flam3.com/flame_draves.pdf . This study adds Markov transition
memory. It uses density rendering, not a physical light simulation.
"""

from __future__ import annotations

import colorsys
import copy
import math
from typing import Any

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

TITLE = "Attractor Families"
DESCRIPTION = "Related nonlinear orbits accumulate luminous folds, with memory between transforms."
CONTROLS = {
    "complexity": {"default": 0.5, "label": "Transform complexity"},
    "persistence": {"default": 0.5, "label": "Orbit persistence"},
    "spread": {"default": 0.5, "label": "Family spread"},
    "glow": {"default": 0.5, "label": "Light diffusion"},
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


def _variation(name: str, x: np.ndarray, y: np.ndarray, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    r2 = x * x + y * y
    if name == "sinusoidal":
        return np.sin(x), np.sin(y)
    if name == "swirl":
        s, c = np.sin(r2), np.cos(r2)
        return x * s - y * c, x * c + y * s
    if name == "spherical":
        d = 1 / (0.17 + r2)
        return x * d, y * d
    if name == "horseshoe":
        d = 1 / np.sqrt(0.04 + r2)
        return (x - y) * (x + y) * d, 2 * x * y * d
    if name == "pdj":
        return np.sin(p[0] * y) - np.cos(p[1] * x), np.sin(p[2] * x) - np.cos(p[3] * y)
    if name == "waves":
        return x + 0.42 * np.sin(p[0] * y), y + 0.36 * np.sin(p[1] * x)
    if name == "bent":
        return np.where(x < 0, x * 1.65, x), np.where(y < 0, y * 0.55, y)
    if name == "disc":
        angle = np.arctan2(y, x) / math.pi
        r = math.pi * np.sqrt(r2)
        return angle * np.sin(r), angle * np.cos(r)
    if name == "curl":
        a = 1 + 0.5 * x + 0.22 * (x * x - y * y)
        b = 0.5 * y + 0.44 * x * y
        d = 1 / (0.10 + a * a + b * b)
        return (x * a + y * b) * d, (y * a - x * b) * d
    return x, y


def _make_function(rng: np.random.Generator, vocabulary: list[str], cfg: dict[str, float]) -> dict[str, Any]:
    angle = float(rng.uniform(-math.pi, math.pi))
    scale_x, scale_y = rng.uniform(0.34, 0.83, 2)
    c, s = math.cos(angle), math.sin(angle)
    matrix = np.array([[c * scale_x, -s * scale_y], [s * scale_x, c * scale_y]])
    selected = rng.choice(vocabulary, size=min(len(vocabulary), 2 + int(cfg["complexity"] > 0.7)), replace=False).tolist()
    weights = rng.dirichlet(np.full(len(selected), 0.8))
    return {
        "matrix": matrix.tolist(),
        "pre_offset": rng.uniform(-0.65, 0.65, 2).tolist(),
        "post_offset": (rng.normal(0, 0.27, 2) * (0.5 + cfg["spread"])).tolist(),
        "variations": selected, "weights": weights.tolist(),
        "parameters": rng.uniform(1.3, 4.1, 4).tolist(),
    }


def _make_program(rng: np.random.Generator, cfg: dict[str, float]) -> dict[str, Any]:
    names = np.array(["sinusoidal", "swirl", "spherical", "horseshoe", "pdj", "waves", "bent", "disc", "curl"])
    vocabulary = rng.choice(names, size=int(rng.integers(3, 6)), replace=False).tolist()
    count = int(rng.integers(3, 6)) + int(cfg["complexity"] * 3)
    layer_count = int(rng.integers(2, 5))
    funcs = []
    hue = float(rng.random())
    colors = []
    for index in range(count):
        funcs.append(_make_function(rng, vocabulary, cfg))
        h = hue + float(rng.uniform(-0.09, 0.09)) + (0.43 if index % 3 == 0 else 0)
        colors.append(colorsys.hsv_to_rgb(h % 1, float(rng.uniform(0.50, 0.85)), 1.0))
    # Every layer shares the transform vocabulary and transition graph, while
    # a modest coefficient perturbation gives it a related, distinct attractor.
    layer_scale = rng.uniform(0.88, 1.12, (layer_count, 2))
    layer_offset = rng.normal(0, 0.22, (layer_count, 2)) * (0.25 + cfg["spread"] * 1.4)
    transition = rng.dirichlet(np.full(count, 0.55), size=count)
    return {
        "vocabulary": vocabulary, "functions": funcs,
        "layer_scale": layer_scale.tolist(), "layer_offset": layer_offset.tolist(),
        "transition": transition.tolist(), "colors": [list(c) for c in colors],
        "base_hue": hue,
    }


def _palette(seed: int) -> dict[str, Any]:
    """A fixed material bank, independent of candidate and transform counts."""
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 81173]))
    hue = float(rng.random())
    colors = []
    for index in range(8):  # Maximum five base transforms plus three additions.
        h = hue + float(rng.uniform(-0.09, 0.09)) + (0.43 if index % 3 == 0 else 0)
        colors.append(list(colorsys.hsv_to_rgb(h % 1, float(rng.uniform(0.50, 0.85)), 1.0)))
    return {"base_hue": hue, "colors": colors}


def _configure_program(neutral: dict[str, Any], cfg: dict[str, float], seed: int,
                       candidate: int, palette: dict[str, Any]) -> dict[str, Any]:
    """Apply controls to a chosen family without replacing its existing functions."""
    program = copy.deepcopy(neutral)
    original_count = len(program["functions"])
    count = original_count + int(cfg["complexity"] * 3) - 1
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 91229, candidate]))
    if count > original_count:
        for _ in range(count - original_count):
            program["functions"].append(_make_function(rng, program["vocabulary"], _settings(None)))
    program["functions"] = program["functions"][:count]
    for function in program["functions"]:
        function["post_offset"] = (np.asarray(function["post_offset"]) * (0.5 + cfg["spread"])).tolist()
    program["layer_offset"] = (np.asarray(program["layer_offset"]) * ((0.25 + cfg["spread"] * 1.4) / 0.95)).tolist()
    if count != original_count:
        base_transition = np.asarray(neutral["transition"])
        transition = rng.uniform(0.03, 0.18, (count, count))
        common = min(count, original_count)
        transition[:common, :common] = base_transition[:common, :common]
        transition /= transition.sum(axis=1, keepdims=True)
        program["transition"] = transition.tolist()
    program["base_hue"] = palette["base_hue"]
    program["colors"] = copy.deepcopy(palette["colors"][:count])
    return program


def _orbits(program: dict[str, Any], rng: np.random.Generator, walkers: int, steps: int,
            persistence: float, burn_in: int = 24) -> tuple[np.ndarray, np.ndarray, dict]:
    funcs = program["functions"]
    count = len(funcs)
    scale = np.asarray(program["layer_scale"])
    offsets = np.asarray(program["layer_offset"])
    colors = np.asarray(program["colors"], dtype=np.float32)
    layer = np.arange(walkers) % len(scale)
    state = rng.integers(0, count, walkers)
    position = rng.normal(0, 0.4, (walkers, 2))
    pigment = colors[state].copy()
    cumulative = np.cumsum(np.asarray(program["transition"]), axis=1)
    cumulative[:, -1] = 1.0
    samples = np.empty((steps * walkers, 2), dtype=np.float32)
    pigments = np.empty((steps * walkers, 3), dtype=np.float32)
    resets, switches = 0, 0
    cached = [(np.asarray(f["matrix"]), np.asarray(f["pre_offset"]), np.asarray(f["post_offset"]),
               f["variations"], f["weights"], np.asarray(f["parameters"])) for f in funcs]
    for iteration in range(steps + burn_in):
        change = rng.random(walkers) > persistence
        indexes = np.flatnonzero(change)
        draws = rng.random(len(indexes))
        new_states = np.sum(draws[:, None] > cumulative[state[indexes]], axis=1)
        switches += int(np.sum(state[indexes] != new_states))
        state[indexes] = new_states
        for fi, (matrix, before, after, names, weights, params) in enumerate(cached):
            mask = state == fi
            if not np.any(mask):
                continue
            p = position[mask]
            u = p[:, 0] * matrix[0, 0] + p[:, 1] * matrix[0, 1] + before[0]
            v = p[:, 0] * matrix[1, 0] + p[:, 1] * matrix[1, 1] + before[1]
            ox, oy = np.zeros_like(u), np.zeros_like(v)
            for name, weight in zip(names, weights):
                vx, vy = _variation(name, u, v, params)
                ox += vx * weight
                oy += vy * weight
            ls, lo = scale[layer[mask]], offsets[layer[mask]]
            position[mask, 0] = (ox + after[0]) * ls[:, 0] + lo[:, 0]
            position[mask, 1] = (oy + after[1]) * ls[:, 1] + lo[:, 1]
        bad = ~np.isfinite(position).all(axis=1) | np.any(np.abs(position) > 30, axis=1)
        if np.any(bad):
            resets += int(bad.sum())
            position[bad] = rng.normal(0, 0.25, (int(bad.sum()), 2))
        pigment = pigment * 0.56 + colors[state] * 0.44
        if iteration >= burn_in:
            begin = (iteration - burn_in) * walkers
            samples[begin:begin + walkers] = position
            pigments[begin:begin + walkers] = pigment
    return samples, pigments, {"escaped_orbit_resets": resets, "transform_switches": switches,
                               "walker_count": walkers, "recorded_steps": steps, "burn_in": burn_in}


def _density(points: np.ndarray, colors: np.ndarray, width: int, height: int,
             bounds: list[float]) -> tuple[np.ndarray, np.ndarray, int]:
    xmin, xmax, ymin, ymax = bounds
    px = (points[:, 0] - xmin) * ((width - 1) / (xmax - xmin))
    py = (points[:, 1] - ymin) * ((height - 1) / (ymax - ymin))
    valid = (px >= 0) & (px < width - 1) & (py >= 0) & (py < height - 1)
    px, py, colors = px[valid], py[valid], colors[valid]
    ix, iy = np.floor(px).astype(np.int32), np.floor(py).astype(np.int32)
    fx, fy = px - ix, py - iy
    size = width * height
    density = np.zeros(size, dtype=np.float64)
    channels = np.zeros((3, size), dtype=np.float64)
    for dx, dy, weight in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                            (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        index = (iy + dy) * width + ix + dx
        density += np.bincount(index, weights=weight, minlength=size)
        for channel in range(3):
            channels[channel] += np.bincount(index, weights=weight * colors[:, channel], minlength=size)
    return density.reshape(height, width), channels.T.reshape(height, width, 3), int(valid.sum())


def render(seed: int, width: int, height: int, controls: dict | None = None) -> tuple[Image.Image, dict]:
    if width < 64 or height < 64:
        raise ValueError("Images must be at least 64 pixels on each side")
    cfg = _settings(controls)
    neutral_cfg = _settings(None)
    rng = np.random.default_rng(int(seed))
    persistence = 0.10 + cfg["persistence"] * 0.74
    neutral_persistence = 0.10 + neutral_cfg["persistence"] * 0.74
    candidates = []
    # Select the seed's family once at neutral controls. Control sweeps must
    # not silently replace the underlying family through a new scout winner.
    for index in range(3):
        program = _make_program(rng, neutral_cfg)
        scout_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 5903, index]))
        points, _, stats = _orbits(program, scout_rng, 768, 30, neutral_persistence)
        lower, upper = np.quantile(points, [0.004, 0.996], axis=0)
        extent = np.maximum(upper - lower, 0.02)
        p = (points - lower) / extent
        inside = np.all((p >= 0) & (p < 1), axis=1)
        cells = np.floor(p[inside] * 48).astype(int)
        coverage = len(np.unique(cells[:, 0] + cells[:, 1] * 48)) / (48 * 48)
        score = coverage - stats["escaped_orbit_resets"] / (768 * 54)
        if float(np.min(extent)) < 0.05:
            score -= 1
        candidates.append((score, index, program, lower, upper))
    score, chosen, program, lower, upper = max(candidates, key=lambda item: item[0])
    palette = _palette(seed)
    program = _configure_program(program, cfg, seed, chosen, palette)
    if any(cfg[name] != neutral_cfg[name] for name in ("complexity", "persistence", "spread")):
        # Reframe the same controlled family; these bounds do not select it.
        scout_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 5903, chosen]))
        points, _, _ = _orbits(program, scout_rng, 768, 30, persistence)
        lower, upper = np.quantile(points, [0.004, 0.996], axis=0)
    center = (lower + upper) * 0.5
    span = np.maximum(upper - lower, 0.02) * 1.16
    aspect = width / height
    if span[0] / span[1] < aspect:
        span[0] = span[1] * aspect
    else:
        span[1] = span[0] / aspect
    bounds = [float(center[0] - span[0] / 2), float(center[0] + span[0] / 2),
              float(center[1] - span[1] / 2), float(center[1] + span[1] / 2)]
    orbit_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 6907, chosen]))
    # Work scales sublinearly with pixel count and remains bounded for previews.
    walkers = 12288
    steps = int(np.clip(140 * math.sqrt(width * height) / 1024, 48, 240))
    points, pigments, stats = _orbits(program, orbit_rng, walkers, steps, persistence)
    density, accumulated, in_frame = _density(points, pigments, width, height, bounds)
    mean_color = accumulated / np.maximum(density[..., None], 1e-8)
    active = density[density > 0]
    exposure = float(np.quantile(np.log1p(active), 0.992)) if len(active) else 1
    light = np.power(np.clip(np.log1p(density) / max(exposure, 1e-6), 0, 1), 1.12)
    emission = mean_color * light[..., None]
    # Bright cores move toward ivory; broad diffusion retains pigment color.
    emission += (light ** 4)[..., None] * 0.25
    pixel_scale = math.sqrt(width * height) / 1024
    glow = cfg["glow"]
    soft = gaussian_filter(emission, (max(0.5, 1.3 * pixel_scale), max(0.5, 1.3 * pixel_scale), 0))
    halo = gaussian_filter(emission, (max(1, 6 * pixel_scale), max(1, 6 * pixel_scale), 0))
    radiance = emission * 1.4 + soft * (0.35 + glow * 0.75) + halo * glow * 0.70
    background = np.asarray(colorsys.hsv_to_rgb((program["base_hue"] + 0.08) % 1, 0.6, 0.022))
    mapped = 1 - np.exp(-radiance * 1.45)
    rgb = np.clip(background[None, None, :] + mapped, 0, 1)
    image = Image.fromarray((rgb * 255 + 0.5).astype(np.uint8))
    return image, {
        "algorithm": "weighted nonlinear iterated transforms with persistent Markov state / density rendering",
        "seed": int(seed), "width": width, "height": height, "controls": cfg,
        "program": program, "candidate_count": len(candidates), "selected_candidate": chosen,
        "candidate_scores": [float(c[0]) for c in candidates], "scout_score": float(score),
        "selection_controls": neutral_cfg, "palette": palette,
        "persistence_probability": persistence, "camera_bounds": bounds,
        "sample_count": int(len(points)), "samples_in_frame": in_frame,
        "density_exposure": exposure, **stats,
    }
