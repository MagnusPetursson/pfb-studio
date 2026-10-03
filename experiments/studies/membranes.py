"""Connected contours expanded by local differential growth.

Sources: Anders Hoff's differential-line (https://github.com/inconvergent/differential-line)
and Nervous System's Floraform (https://n-e-r-v-o-u-s.com/projects/sets/floraform/).
This is an independent 2D study: attraction along contour edges, short-range
repulsion via a spatial tree, spatially varying growth, and edge subdivision.
Open/closed curves retain their initial connectivity; this does not simulate
biological tissue, split contours, or guarantee intersection-free geometry.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

TITLE = "Growing membranes"
DESCRIPTION = "Connected contours buckle into folded membranes; successive growth stages leave fine colored traces."
CONTROLS = {
    "growth": {"default": 0.5, "label": "Growth duration"},
    "repulsion": {"default": 0.5, "label": "Fold spacing"},
    "anisotropy": {"default": 0.5, "label": "Uneven growth"},
    "history": {"default": 0.5, "label": "History visibility"},
}


def _controls(values):
    supplied = values or {}
    unknown = set(supplied) - set(CONTROLS)
    if unknown:
        raise ValueError(f"Unknown membrane controls: {sorted(unknown)}")
    result = {k: float(supplied.get(k, v["default"])) for k, v in CONTROLS.items()}
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in result.values()):
        raise ValueError("Membrane controls must be finite values in [0, 1]")
    return result


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def render(seed: int, width: int, height: int, controls: dict | None = None):
    """Return an RGB image and reproducible, JSON-serializable study metadata."""
    if width < 1 or height < 1:
        raise ValueError("Image dimensions must be positive")
    c = _controls(controls)
    rng = np.random.default_rng(seed)
    extent = np.array([width, height], dtype=float) / min(width, height)
    # Several unequal contours, arranged along a crooked axis, leave openings
    # between colonies. Some seeds substitute an open ribbon for a closed lobe.
    angle = rng.uniform(-math.pi, math.pi)
    axis = np.array([math.cos(angle), math.sin(angle)])
    cross = np.array([-axis[1], axis[0]])
    count = int(rng.integers(2, 6))
    spread = rng.uniform(0.32, 0.57)
    offsets = np.linspace(-spread / 2, spread / 2, count)
    curves, closed, phases, rates = [], [], [], []
    for i, offset in enumerate(offsets):
        center = extent / 2 + axis * offset + cross * rng.uniform(-0.13, 0.13)
        radius = rng.uniform(0.070, 0.145) * (1.0 if count < 4 else 0.8)
        local_angle = angle + rng.uniform(-1.0, 1.0)
        rotation = np.array([[math.cos(local_angle), -math.sin(local_angle)],
                             [math.sin(local_angle), math.cos(local_angle)]])
        is_closed = bool(rng.random() > 0.30)
        # Polar harmonics yield unequal lobes without hard-coding a flower.
        phase = rng.uniform(0, 2 * math.pi, 3)
        n = int(rng.integers(34, 55))
        t = np.linspace(0, 2 * math.pi if is_closed else rng.uniform(3.4, 5.3), n,
                        endpoint=not is_closed) + phase[0]
        radial = 1 + 0.19 * np.sin(2 * t + phase[1]) + 0.08 * np.cos(3 * t + phase[2])
        aspect = rng.uniform(1.15, 2.35)
        points = np.column_stack([radius * aspect * radial * np.cos(t),
                                  radius / math.sqrt(aspect) * radial * np.sin(t)])
        curves.append(points @ rotation.T + center)
        closed.append(is_closed)
        phases.append(phase)
        rates.append(float(rng.uniform(0.70, 1.25)))

    initial_nodes = sum(map(len, curves))
    steps = int(150 + 210 * c["growth"])
    neighbor_radius = 0.012 + 0.016 * c["repulsion"]
    split_length = 0.0075
    max_nodes = 4200
    history = [[p.copy() for p in curves]]
    snapshot_steps = set(np.linspace(5, steps - 1, 19).astype(int))
    # A displaced ellipse protects negative space. It is an exclusion region,
    # not a clipping mask: nodes respond to it during growth.
    void_center = extent / 2 + cross * rng.uniform(-0.17, 0.17) + axis * rng.uniform(-0.1, 0.1)
    void_axes = np.array([rng.uniform(0.035, 0.07), rng.uniform(0.04, 0.085)])

    def growth_field(p, phase):
        # Coarse and fine wavelengths create broad folds beside tighter
        # seams. This field is fixed in space, rather than per-step jitter.
        coarse = np.sin(p[:, 0] * 7.3 + phase[0]) * np.cos(p[:, 1] * 5.1 + phase[1])
        fine = np.sin(p[:, 0] * 17.0 + p[:, 1] * 6.0 + phase[2])
        return (coarse + 0.45 * fine) / 1.45

    inserted = 0
    for step in range(steps):
        lengths = [len(p) for p in curves]
        starts = np.cumsum([0] + lengths)
        points = np.concatenate(curves)
        variation = 0.28 + 0.65 * c["anisotropy"]
        spacing = np.concatenate([
            neighbor_radius * (1 + variation * growth_field(p, phase))
            for p, phase in zip(curves, phases)
        ])
        force = np.zeros_like(points)
        pairs = cKDTree(points).query_pairs(float(spacing.max()), output_type="ndarray")
        if len(pairs):
            # Adjacent contour nodes are handled by springs, not repulsion.
            next_index = np.arange(len(points)) + 1
            for start, n, loop in zip(starts, lengths, closed):
                next_index[start + n - 1] = start if loop else -1
            keep = (next_index[pairs[:, 0]] != pairs[:, 1]) & (next_index[pairs[:, 1]] != pairs[:, 0])
            pairs = pairs[keep]
            delta = points[pairs[:, 0]] - points[pairs[:, 1]]
            distance = np.maximum(np.linalg.norm(delta, axis=1), 1e-8)
            pair_spacing = (spacing[pairs[:, 0]] + spacing[pairs[:, 1]]) / 2
            repel = delta / distance[:, None] * np.maximum(1 - distance / pair_spacing, 0)[:, None]
            np.add.at(force, pairs[:, 0], repel)
            np.add.at(force, pairs[:, 1], -repel)
        new_curves = []
        for i, (p, loop) in enumerate(zip(curves, closed)):
            previous, following = np.roll(p, 1, axis=0), np.roll(p, -1, axis=0)
            if not loop:
                previous[0], following[-1] = p[0], p[-1]
            tangent = _unit(following - previous)
            normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
            # Spatial variation persists as the contour evolves. It creates
            # local folds rather than random jitter independently each step.
            ph = phases[i]
            uneven = growth_field(p, ph)
            rate = rates[i] * (1 + c["anisotropy"] * 0.8 * uneven)
            laplacian = (previous + following) / 2 - p
            velocity = force[starts[i]:starts[i + 1]] * (0.0011 * rate[:, None])
            velocity += laplacian * 0.15
            velocity += normal * (0.00026 * rate[:, None])
            # Elastic separation of consecutive vertices counters collapse.
            for neighbor in (previous, following):
                d = p - neighbor
                length = np.linalg.norm(d, axis=1)
                velocity += _unit(d) * np.maximum(0.0045 - length, 0)[:, None] * 0.16
            q = (p - void_center) / void_axes
            radial = np.linalg.norm(q, axis=1)
            velocity += _unit(q / void_axes) * np.maximum(1.10 - radial, 0)[:, None] * 0.0018
            if not loop:
                velocity[[0, -1]] *= 0.12
            speed = np.linalg.norm(velocity, axis=1)
            velocity *= np.minimum(1, 0.0020 / np.maximum(speed, 1e-12))[:, None]
            # Growth has no rectangular wall. Bounded steps/nodes control
            # work; a single composition fit below handles image framing.
            p = p + velocity
            new_curves.append(p)
        curves = new_curves
        # Subdivision is bounded and ordered; inserting an edge midpoint
        # preserves the path and introduces no stochastic work-order effects.
        remaining = max_nodes - sum(map(len, curves))
        if remaining > 0:
            for i, (p, loop) in enumerate(zip(curves, closed)):
                end = len(p) if loop else len(p) - 1
                edges = np.linalg.norm(np.roll(p, -1, axis=0) - p, axis=1)
                chosen = np.flatnonzero(edges[:end] > split_length)[:remaining]
                if len(chosen):
                    expanded = np.empty((len(p) + len(chosen), 2))
                    slots = np.arange(len(p)) + np.searchsorted(chosen, np.arange(len(p)))
                    expanded[slots] = p
                    expanded[slots[chosen] + 1] = (p[chosen] + p[(chosen + 1) % len(p)]) / 2
                    curves[i] = expanded
                    remaining -= len(chosen)
                    inserted += len(chosen)
        if step in snapshot_steps:
            history.append([p.copy() for p in curves])

    palettes = [((239, 231, 211), (26, 74, 82), (175, 71, 47)),
                ((230, 232, 217), (33, 76, 68), (129, 91, 42)),
                ((235, 224, 212), (76, 50, 83), (191, 88, 53)),
                ((230, 235, 232), (34, 66, 103), (148, 78, 46))]
    paper, ink, accent = palettes[int(rng.integers(len(palettes)))]
    scale = 2
    image = Image.new("RGB", (width * scale, height * scale), paper)
    draw = ImageDraw.Draw(image, "RGBA")
    pixel_scale = min(width, height) * scale
    all_points = np.concatenate([p for stage in history for p in stage])
    bounds_low, bounds_high = all_points.min(axis=0), all_points.max(axis=0)
    span = np.maximum(bounds_high - bounds_low, 1e-9)
    frame_margin = 0.055 + 0.030 * (0.5 + 0.5 * math.sin(phases[0][0]))
    frame_scale = min(1.0, float(np.min((extent - 2 * frame_margin) / span)))
    source_center = (bounds_low + bounds_high) / 2
    desired_center = extent / 2 + axis * (0.04 * math.sin(phases[0][1]))
    framed_span = span * frame_scale
    target_center = np.clip(desired_center, frame_margin + framed_span / 2,
                            extent - frame_margin - framed_span / 2)

    def framed(p):
        return (p - source_center) * frame_scale + target_center

    for i, (p, loop) in enumerate(zip(curves, closed)):
        if loop:
            wash = accent if i % 3 == 1 else ink
            draw.polygon([tuple(v) for v in framed(p) * pixel_scale], fill=(*wash, 13))
    for stage, contours in enumerate(history):
        progress = stage / max(len(history) - 1, 1)
        for i, (p, loop) in enumerate(zip(contours, closed)):
            mix = np.clip(0.13 + 0.63 * progress + 0.14 * math.sin(i * 2.4), 0, 1)
            color = tuple(int(a * (1 - mix) + b * mix) for a, b in zip(accent, ink))
            xy = [tuple(v) for v in framed(p) * pixel_scale]
            if loop:
                xy.append(xy[0])
            alpha = int((42 + 110 * c["history"]) * (0.42 + progress * 0.58))
            line_width = max(1, round(pixel_scale / 1500))
            if stage == len(history) - 1:
                alpha = 235
                line_width = max(1, round(pixel_scale / 1050))
            draw.line(xy, fill=(*color, alpha), width=line_width, joint="curve")
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    # Very low-amplitude paper grain is generated independently of simulation.
    texture_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 781]))
    noise = texture_rng.normal(0, 0.50, (height, width, 1))
    image = Image.fromarray(np.clip(np.asarray(image, dtype=float) + noise, 0, 255).astype(np.uint8))
    return image, {
        "study": "membranes", "seed": int(seed), "controls": c,
        "steps": steps, "contours": count, "closed_contours": sum(closed),
        "open_contours": count - sum(closed), "initial_nodes": initial_nodes,
        "final_nodes": sum(map(len, curves)), "inserted_nodes": inserted,
        "node_limit": max_nodes, "history_layers": len(history),
        "frame_margin": frame_margin, "frame_scale": frame_scale,
        "framed_bounds": [framed(bounds_low).tolist(), framed(bounds_high).tolist()],
        "growth_bounds": [bounds_low.tolist(), bounds_high.tolist()],
        "spacing_range": [float(spacing.min()), float(spacing.max())],
        "finite_geometry": bool(all(np.isfinite(p).all() for p in curves)),
        "algorithm": "connected-contour differential growth with cKDTree repulsion",
    }
