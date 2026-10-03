"""Ray focusing in a smooth Perlin potential, rendered as deposited radiance.

Mechanism: Hamiltonian transport x'=p, p'=-grad(V), rather than advection by
an incompressible velocity field. Rays may cross in position while retaining
different momenta; their projected density therefore develops caustics.
Inspired by Patsyk et al., Observation of branched flow of light (2020):
https://www.nature.com/articles/s41586-020-2376-8 . This is an artistic weak-
potential ray model, not a wave-optics or physical radiometry simulation.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import map_coordinates

from .perlin_common import Perlin, density_image, splat

TITLE = "Branched light"
DESCRIPTION = "Smooth Perlin refraction concentrates moving ray bundles into fine luminous caustics on black."
CONTROLS = {
    "refraction": {"default": 0.5, "label": "Refraction strength"},
    "distance": {"default": 0.5, "label": "Travel distance"},
}


def _controls(values):
    values = values or {}
    unknown = set(values) - set(CONTROLS)
    if unknown:
        raise ValueError(f"Unknown branched-light controls: {sorted(unknown)}")
    result = {name: float(values.get(name, spec["default"])) for name, spec in CONTROLS.items()}
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in result.values()):
        raise ValueError("Controls must be finite values in [0, 1]")
    return result


def _scene(seed):
    rng = np.random.default_rng(seed)
    scene = {
        "perlin_seed": int(rng.integers(0, 2**31)),
        "frequency": float(rng.uniform(2.4, 5.5)),
        "anisotropy": float(rng.uniform(.65, 1.45)),
        "field_angle": float(rng.uniform(-math.pi, math.pi)),
        "warp": float(rng.uniform(.06, .25)),
        "offset": rng.uniform(-20, 20, 2).tolist(),
        "launches": [],
    }
    for _ in range(int(rng.integers(2, 5))):
        scene["launches"].append({
            "center": rng.uniform(-.66, .66, 2).tolist(),
            "angle": float(rng.uniform(-math.pi, math.pi)),
            "width": float(rng.uniform(.35, 1.05)),
            "bend": float(rng.uniform(-.24, .24)),
            "distance_ratio": float(rng.uniform(.68, 1.18)),
            "weight": float(rng.uniform(.5, 1.0)),
        })
    scene["tint"] = [205, 225, 255]
    return scene


def _potential(scene, aspect):
    # Fixed world sampling: changing output pixel count leaves transport intact.
    grid_h, grid_w = 544, max(192, min(1024, int(round(544 * aspect))))
    bounds = [-1.35 * aspect, 1.35 * aspect, -1.35, 1.35]
    xs = np.linspace(bounds[0], bounds[1], grid_w)
    ys = np.linspace(bounds[2], bounds[3], grid_h)
    x, y = np.meshgrid(xs, ys)
    c, s = math.cos(scene["field_angle"]), math.sin(scene["field_angle"])
    u, v = c * x - s * y, s * x + c * y
    noise = Perlin(scene["perlin_seed"])
    ox, oy = scene["offset"]
    wx = u + scene["warp"] * noise.noise2(u * .8 + 37.1, v * .8 - 11.3)
    wy = v + scene["warp"] * noise.noise2(u * .8 - 7.6, v * .8 + 24.9)
    f = scene["frequency"]
    potential = noise.noise2(wx * f + ox, wy * f * scene["anisotropy"] + oy)
    potential += .18 * noise.noise2(wx * f * 2.3 - 13.4, wy * f * 2.3 + 5.7)
    gy, gx = np.gradient(potential, ys[1] - ys[0], xs[1] - xs[0])
    return potential, np.asarray([gx, gy]), bounds


def _force(gradient, position, bounds, strength):
    h, w = gradient.shape[1:]
    x = (position[:, 0] - bounds[0]) * ((w - 1) / (bounds[1] - bounds[0]))
    y = (position[:, 1] - bounds[2]) * ((h - 1) / (bounds[3] - bounds[2]))
    coordinates = np.asarray([y, x])
    return -strength * np.stack([map_coordinates(g, coordinates, order=1, mode="nearest", prefilter=False)
                                 for g in gradient], axis=1)


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 64 or height < 64:
        raise ValueError("Images must be at least 64 pixels on each side")
    cfg = _controls(controls)
    scene = _scene(int(seed))
    aspect = width / height
    potential, gradient, bounds = _potential(scene, aspect)
    strength = .85 * cfg["refraction"]
    distance = 1.1 + 2.0 * cfg["distance"]
    ds = .0027
    positions, momenta, lifetimes, weights = [], [], [], []
    count_per_launch = 4608
    for launch in scene["launches"]:
        t = np.linspace(-.5, .5, count_per_launch)
        direction = np.array([math.cos(launch["angle"]), math.sin(launch["angle"])])
        tangent = np.array([-direction[1], direction[0]])
        center = np.asarray(launch["center"]) * np.array([aspect, 1])
        transverse = t * launch["width"]
        positions.append(center + transverse[:, None] * tangent +
                         (launch["bend"] * transverse**2)[:, None] * direction)
        # A curved initial wavefront launches along its local normal.
        p = direction - (2 * launch["bend"] * transverse)[:, None] * tangent
        p /= np.linalg.norm(p, axis=1, keepdims=True)
        momenta.append(p)
        lifetimes.append(np.full(count_per_launch, distance * launch["distance_ratio"]))
        weights.append((np.cos(t * math.pi)**2) * launch["weight"] * launch["width"] / count_per_launch)
    position = np.concatenate(positions)
    momentum = np.concatenate(momenta)
    lifetime = np.concatenate(lifetimes)
    weight = np.concatenate(weights)
    initial_position, initial_momentum = position.copy(), momentum.copy()
    age = np.zeros(len(position))
    sampling_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 19873]))
    first_step = sampling_rng.uniform(.05 * ds, ds, len(position))
    density = np.zeros((height, width), dtype=np.float64)
    acceleration = _force(gradient, position, bounds, strength)
    maximum_steps = int(math.ceil(float(lifetime.max()) / ds))
    samples = 0
    active = np.ones(len(position), dtype=bool)
    block_x, block_y, block_weight = [], [], []
    for step in range(maximum_steps):
        # Velocity Verlet; forces bend momentum, they do not prescribe velocity.
        # Stagger the initial sample times to avoid coherent raster bands.
        dt = first_step[active] if step == 0 else np.full(int(active.sum()), ds)
        momentum[active] += .5 * dt[:, None] * acceleration[active]
        position[active] += dt[:, None] * momentum[active]
        age[active] += dt
        acceleration[active] = _force(gradient, position[active], bounds, strength)
        momentum[active] += .5 * dt[:, None] * acceleration[active]
        active &= ((age < lifetime) & (np.abs(position[:, 0]) < 1.3 * aspect) &
                   (np.abs(position[:, 1]) < 1.3))
        visible = active & (np.abs(position[:, 0]) < aspect) & (np.abs(position[:, 1]) < 1)
        if np.any(visible):
            block_x.append((position[visible, 0] / aspect + 1) * (width - 1) / 2)
            block_y.append((position[visible, 1] + 1) * (height - 1) / 2)
            # Smooth finite travel ending; all brightness still comes from rays.
            fade = np.minimum(1, (lifetime[visible] - age[visible]) / .18)
            fade *= np.minimum(1, age[visible] / .28)**2
            block_weight.append(weight[visible] * fade * ds)
            samples += int(visible.sum())
        if (step + 1) % 24 == 0 or step == maximum_steps - 1 or not active.any():
            if block_x:
                splat(density, np.concatenate(block_x), np.concatenate(block_y), np.concatenate(block_weight))
                block_x, block_y, block_weight = [], [], []
        if not active.any():
            break
    nonzero = density[density > 0]
    exposure = float(np.quantile(nonzero, .985)) if len(nonzero) else 1.0
    image = density_image(density, exposure=exposure, tint=tuple(scene["tint"]))
    ballistic = initial_position + initial_momentum * age[:, None]
    displacement = np.linalg.norm(position - ballistic, axis=1)
    return image, {
        "algorithm": "Hamiltonian ray focusing in a warped Perlin potential; velocity Verlet; bilinear radiance accumulation",
        "seed": int(seed), "width": width, "height": height, "controls": cfg,
        "scene": scene, "potential_grid": [int(potential.shape[1]), int(potential.shape[0])],
        "potential_bounds": bounds, "potential_standard_deviation": float(potential.std()),
        "potential_strength": strength, "integration_step": ds,
        "sample_phase": "seeded first-step offsets in [0.05*ds, ds]; then constant ds",
        "integration_steps": step + 1, "ray_count": len(position), "ray_samples_in_frame": samples,
        "travel_distance": distance, "density_exposure": exposure,
        "density_maximum": float(density.max()), "nonzero_pixels": int(len(nonzero)),
        "mean_displacement_from_ballistic": float(displacement.mean()),
        "maximum_displacement_from_ballistic": float(displacement.max()),
        "mean_momentum_change": float(np.linalg.norm(momentum - initial_momentum, axis=1).mean()),
        "background": [0, 0, 0], "bloom": False, "texture_overlay": False,
    }
