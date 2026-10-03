"""Thin material sheets transported through a numerical 3D Perlin curl field.

An independent particle-advection study, informed by the fine flow striations
of PFB's Perlin generator and the overlapping surfaces of its Fujii generator.
Three Perlin scalar potentials define a vector potential; central differences
produce its curl. A padded, nonperiodic grid is sampled with trilinear
interpolation and translated slowly through time. Sheet particles move with
midpoint integration, then a seeded orthographic camera projects their folds.
Density comes only from projected transported particles, with no blur, bloom,
paper, grain overlay, or radial emitter. This is an artistic transport model,
not a fluid solver. Numerical interpolation only approximates a continuous curl.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.ndimage import map_coordinates

from .perlin_common import Perlin, density_image, splat

TITLE = "Folded veils"
DESCRIPTION = "Irregular particle sheets fold through three-dimensional Perlin flow, leaving pale wisps on black."
CONTROLS = {
    "folding": {"default": 0.5, "label": "Folding time"},
    "complexity": {"default": 0.5, "label": "Fine flow strength"},
}


def _controls(values):
    values = values or {}
    unknown = set(values) - set(CONTROLS)
    if unknown:
        raise ValueError(f"Unknown veil controls: {sorted(unknown)}")
    result = {k: float(values.get(k, spec["default"])) for k, spec in CONTROLS.items()}
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in result.values()):
        raise ValueError("Veil controls must be finite values in [0, 1]")
    return result


def _curl_field(perlin, offsets, frequency, complexity):
    size = 80
    half_extent = 4.5
    coordinates = np.linspace(-half_extent, half_extent, size)
    spacing = coordinates[1] - coordinates[0]
    x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    potentials = []
    for offset in offsets:
        broad = perlin.noise3(x * frequency + offset[0], y * frequency + offset[1], z * frequency + offset[2])
        fine = perlin.noise3(x * frequency * 2.3 + offset[0] + 31.7,
                             y * frequency * 2.3 + offset[1] - 17.3,
                             z * frequency * 2.3 + offset[2] + 11.9)
        potentials.append(broad + (0.12 + 0.28 * complexity) * fine)
    ax, ay, az = potentials
    field = np.array([
        np.gradient(az, spacing, axis=1) - np.gradient(ay, spacing, axis=2),
        np.gradient(ax, spacing, axis=2) - np.gradient(az, spacing, axis=0),
        np.gradient(ay, spacing, axis=0) - np.gradient(ax, spacing, axis=1),
    ])
    # A single global scaling preserves the relative speeds and the curl's
    # structure. Normalizing each local vector would change the transport.
    rms = float(np.sqrt(np.mean(np.sum(field * field, axis=0))))
    field /= max(rms, 1e-12)
    return field, half_extent, spacing, rms


def _make_sheets(seed):
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 2917]))
    source_noise = Perlin(int(rng.integers(0, 2**31)))
    count = int(rng.integers(2, 5))
    total = 76000
    allocation = rng.dirichlet(np.full(count, 2.5))
    amounts = np.maximum(6000, (allocation * total).astype(int))
    amounts[-1] += total - int(amounts.sum())
    # The last adjustment must remain positive even for an extreme draw.
    if amounts[-1] < 6000:
        amounts = np.full(count, total // count)
        amounts[-1] += total - int(amounts.sum())
    major_axis = rng.normal(size=3)
    major_axis /= np.linalg.norm(major_axis)
    clouds = []
    descriptions = []
    for i, amount in enumerate(amounts):
        center = major_axis * ((i / (count - 1) - 0.5) * rng.uniform(0.65, 1.25))
        center += rng.uniform(-0.20, 0.20, 3)
        basis, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        axes = rng.uniform([0.50, 0.24], [0.92, 0.57])
        offset = rng.uniform(-40, 40, 2)
        batches = []
        remaining = int(amount)
        for _ in range(8):
            candidate = rng.uniform(-1.18, 1.18, (max(remaining * 2, 1000), 2))
            u, v = candidate.T
            boundary = source_noise.noise2(u * 1.45 + offset[0], v * 1.45 + offset[1])
            interior = u * u + v * v + 0.31 * boundary < 0.93
            # A seeded off-center aperture makes some sheets open or torn.
            aperture = source_noise.noise2(u * 2.7 + offset[0] + 8.3, v * 2.7 + offset[1] - 4.1)
            selected = candidate[interior & (aperture > -0.37)][:remaining]
            batches.append(selected)
            remaining -= len(selected)
            if remaining == 0:
                break
        if remaining:
            raise RuntimeError("Could not sample a nonempty Perlin sheet")
        uv = np.concatenate(batches)
        ripple = source_noise.noise2(uv[:, 0] * 2.2 + offset[0], uv[:, 1] * 2.2 + offset[1]) * 0.055
        local = np.column_stack([uv[:, 0] * axes[0], uv[:, 1] * axes[1], ripple])
        clouds.append(local @ basis.T + center)
        descriptions.append({"center": center.tolist(), "axes": axes.tolist(),
                             "orientation": basis.tolist(), "particles": int(amount)})
    return np.concatenate(clouds), descriptions


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 1 or height < 1:
        raise ValueError("Image dimensions must be positive")
    c = _controls(controls)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 8311]))
    noise_seed = int(rng.integers(0, 2**31))
    perlin = Perlin(noise_seed)
    offsets = rng.uniform(-55, 55, (3, 3))
    frequency = float(rng.uniform(0.57, 0.87))
    field, half_extent, spacing, field_rms = _curl_field(perlin, offsets, frequency, c["complexity"])
    drift = rng.normal(size=3)
    drift *= rng.uniform(0.045, 0.09) / np.linalg.norm(drift)
    camera, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    camera_offset = rng.uniform(-0.055, 0.055, 2)
    points, sources = _make_sheets(seed)
    initial_count = len(points)
    initial_bounds = [points.min(axis=0).tolist(), points.max(axis=0).tolist()]
    steps = int(66 + 76 * c["folding"])
    dt = 0.023
    escaped = 0
    boundary_queries = 0

    def velocity(p, t):
        nonlocal boundary_queries
        query = p + drift * t
        boundary_queries += int(np.count_nonzero(np.any(np.abs(query) >= half_extent - spacing, axis=1)))
        coords = ((query + half_extent) / spacing).T
        return np.column_stack([map_coordinates(component, coords, order=1, mode="nearest", prefilter=False)
                                for component in field])

    def advance(p, t, h):
        middle = p + velocity(p, t) * (h / 2)
        return p + velocity(middle, t + h / 2) * h

    def keep_interior(p, t):
        nonlocal escaped
        # Discard before the padded field edge; never wrap or clamp a
        # particle into an artificial wall. Apply this to every advance,
        # including the close time samples used for light deposition.
        interior = (np.abs(p + drift * t) < half_extent - spacing * 3).all(axis=1)
        escaped += int(np.count_nonzero(~interior))
        p = p[interior]
        if not len(p):
            raise RuntimeError("All veil particles escaped the padded flow domain")
        return p

    time = 0.0
    for _ in range(steps):
        points = advance(points, time, dt)
        time += dt
        points = keep_interior(points, time)

    # Eight nearby physical time samples improve density without painting a
    # long exposure through the entire volume occupied during sheet folding.
    snapshots = []
    for sample in range(8):
        snapshots.append(points @ camera[:, :2])
        if sample < 7:
            points = advance(points, time, 0.0015)
            time += 0.0015
            points = keep_interior(points, time)
    all_projected = np.concatenate(snapshots)
    low, high = all_projected.min(axis=0), all_projected.max(axis=0)
    span = np.maximum(high - low, 1e-9)
    canvas_extent = np.array([width, height], dtype=float) / min(width, height)
    fit = float(np.min(canvas_extent * 0.84 / span))
    center = (low + high) / 2
    destination = canvas_extent / 2 + camera_offset
    density = np.zeros((height, width), dtype=np.float64)
    for snapshot in snapshots:
        projected = ((snapshot - center) * fit + destination) * min(width, height)
        splat(density, projected[:, 0], projected[:, 1], 1.0 / len(snapshots))
    image = density_image(density)
    return image, {
        "study": "folded_veils", "seed": int(seed), "controls": c,
        "particles": initial_count, "retained_particles": len(points),
        "escaped_particles": escaped, "boundary_queries": boundary_queries,
        "sheets": sources, "sheet_count": len(sources),
        "steps": steps, "time_step": dt, "final_time_samples": len(snapshots),
        "noise_seed": noise_seed, "field_frequency": frequency,
        "field_grid": list(field.shape[1:]), "field_half_extent": half_extent,
        "field_rms_before_scaling": field_rms, "field_translation": drift.tolist(),
        "camera": camera.tolist(), "camera_offset": camera_offset.tolist(),
        "initial_bounds": initial_bounds,
        "world_bounds": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
        "projected_bounds": [low.tolist(), high.tolist()], "projection_scale": fit,
        "finite_geometry": bool(np.isfinite(points).all()),
        "positive_density_pixels": int(np.count_nonzero(density)),
        "black_pixels": int(np.count_nonzero(np.all(np.asarray(image) == 0, axis=2))),
        "algorithm": "irregular particle sheets advected through translated 3D Perlin curl",
    }
