"""Perlin currents traced by particles with distinct velocity response times.

The field construction uses the curl of a smooth noise potential, following
Bridson, Hourihan and Nordenstam, Curl-Noise for Procedural Fluid Flow (2007):
https://www.cs.ubc.ca/~rbridson/docs/bridson-siggraph2007-curlnoise.pdf
The particles instead retain velocity: dv/dt = (flow(position, time)-v)/tau.
This is an artistic inertial-tracer model, not a fluid or light simulation.
Filament texture comes from deposited trajectories; there is no image grain,
background texture, blur or bloom. World-space simulation ignores image size.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.ndimage import map_coordinates

from experiments.studies.perlin_common import Perlin, density_image, splat

TITLE = "Inertial filaments"
DESCRIPTION = "Unequal particle response times pull thin luminous strands through changing Perlin currents."
CONTROLS = {
    "inertia": {"default": 0.5, "label": "Momentum separation"},
    "turbulence": {"default": 0.5, "label": "Fine currents"},
}

_STEPS = 720
_DT = 0.018
_GRID = 224
_DOMAIN = 5.5


def _settings(controls: dict | None) -> dict[str, float]:
    values = {name: float(spec["default"]) for name, spec in CONTROLS.items()}
    for name, value in (controls or {}).items():
        if name not in values:
            raise ValueError(f"Unknown control: {name}")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be finite and in [0, 1]")
        values[name] = value
    return values


def _relax_velocity(velocity: np.ndarray, target: np.ndarray,
                    response: np.ndarray, dt: float) -> np.ndarray:
    """Exact drag relaxation for a target held constant during one small step."""
    return velocity + (target - velocity) * (-np.expm1(-dt / response[:, None]))


def _program(seed: int) -> dict:
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 41927]))
    count = int(rng.integers(2, 6))
    emitters = []
    for _ in range(count):
        emitters.append({
            "center": rng.uniform(-1.05, 1.05, 2).tolist(),
            "angle": float(rng.uniform(-math.pi, math.pi)),
            "length": float(rng.uniform(0.14, 0.58)),
            "bend": float(rng.uniform(-0.7, 0.7)),
            "bundles": int(rng.integers(3, 7)),
            "kick": rng.uniform(-0.12, 0.12, 2).tolist(),
        })
    return {
        "emitters": emitters,
        "large_scale": float(rng.uniform(0.36, 0.79)),
        "fine_scale": float(rng.uniform(1.55, 2.65)),
        "anisotropy": float(rng.uniform(0.72, 1.55)),
        "noise_offset": rng.uniform(-70, 70, 3).tolist(),
        "drift": rng.uniform(-0.065, 0.065, 2).tolist(),
        "time_rate": float(rng.uniform(0.045, 0.105)),
        "field_rotation": float(rng.uniform(-math.pi, math.pi)),
    }


def _fields(seed: int, cfg: dict, program: dict) -> np.ndarray:
    """Seven nonperiodic snapshots; interpolate in time, never wrap the grid."""
    yy, xx = np.mgrid[-_DOMAIN:_DOMAIN:complex(_GRID),
                      -_DOMAIN:_DOMAIN:complex(_GRID)]
    angle = program["field_rotation"]
    cs, sn = math.cos(angle), math.sin(angle)
    u = (xx * cs - yy * sn) * program["anisotropy"]
    v = (xx * sn + yy * cs) / program["anisotropy"]
    ox, oy, oz = program["noise_offset"]
    low, fine = program["large_scale"], program["fine_scale"]
    noise = Perlin(seed)
    fields = []
    spacing = 2 * _DOMAIN / (_GRID - 1)
    normalization = None
    for time in np.linspace(0, _STEPS * _DT, 7):
        z = oz + time * program["time_rate"]
        potential = noise.noise3(u * low + ox, v * low + oy, z) / low
        # Potential amplitude accounts for differentiation's frequency factor.
        potential += (0.07 + 0.18 * cfg["turbulence"]) / fine * noise.noise3(
            u * fine + ox + 19.7, v * fine + oy - 26.2, z * 0.7 + 38.1)
        dy, dx = np.gradient(potential, spacing)
        velocity = np.stack((dy, -dx), axis=0)
        if normalization is None:
            normalization = 0.31 / max(float(np.sqrt(np.mean(velocity ** 2))), 1e-6)
        velocity *= normalization
        velocity[0] += program["drift"][0]
        velocity[1] += program["drift"][1]
        fields.append(velocity.astype(np.float32))
    return np.stack(fields)


def _launch(seed: int, program: dict, cfg: dict):
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 51241]))
    origins, kicks, strengths = [], [], []
    for emitter in program["emitters"]:
        center = np.asarray(emitter["center"])
        cs, sn = math.cos(emitter["angle"]), math.sin(emitter["angle"])
        tangent, normal = np.array((cs, sn)), np.array((-sn, cs))
        # Broken narrow sources, with unequal bundle weights and fine strands.
        for along in np.sort(rng.uniform(-0.5, 0.5, emitter["bundles"])):
            count = int(rng.integers(48, 77))
            offset = along + rng.normal(0, 0.015, count)
            points = (center + offset[:, None] * emitter["length"] * tangent
                      + (emitter["bend"] * offset ** 2 * emitter["length"]
                         + rng.normal(0, 0.0025, count))[:, None] * normal)
            origins.append(points)
            kicks.append(np.tile(emitter["kick"], (count, 1)))
            strengths.append(rng.lognormal(-0.3, 0.55, count) * rng.uniform(0.4, 1.4))
    origin = np.concatenate(origins).astype(np.float32)
    kick = np.concatenate(kicks).astype(np.float32)
    strength = np.concatenate(strengths).astype(np.float32)
    # All three cohorts start identically: later separation is caused by inertia.
    times = np.array((0.025, 0.11 + cfg["inertia"] * 0.32,
                      0.28 + cfg["inertia"] * 1.3), dtype=np.float32)
    count = len(origin)
    # Each strand keeps its own response time throughout the run. Small fixed
    # differences open fine fans inside the three larger dynamical cohorts.
    response_spread = rng.uniform(0.84, 1.16, count).astype(np.float32)
    lifetime = rng.uniform(0.58, 0.91, count).astype(np.float32) * _STEPS
    tendrils = rng.random(count) < 0.07
    lifetime[tendrils] = _STEPS
    return (np.tile(origin, (3, 1)), np.tile(kick, (3, 1)),
            np.tile(strength, 3), (times[:, None] * response_spread).ravel(),
            np.tile(lifetime, 3), count, times)


def _sample(field: np.ndarray, position: np.ndarray) -> np.ndarray:
    coordinates = ((position[:, ::-1] + _DOMAIN) * ((_GRID - 1) / (2 * _DOMAIN))).T
    return np.column_stack([map_coordinates(component, coordinates, order=1,
                                            mode="nearest", prefilter=False)
                            for component in field])


def _advance_particles(position: np.ndarray, velocity: np.ndarray,
                       active: np.ndarray, dt: float):
    proposed = position + velocity * dt
    escaped = active & (np.abs(proposed).max(axis=1) > _DOMAIN)
    # Stop at the last valid sample; never clamp trajectories onto a frame edge.
    return np.where((active & ~escaped)[:, None], proposed, position), escaped


def _simulate(seed: int, cfg: dict):
    program = _program(seed)
    fields = _fields(seed, cfg, program)
    position, kick, strength, response, lifetime, count, times = _launch(seed, program, cfg)
    velocity = _sample(fields[0], position) + kick
    history = np.empty((_STEPS + 1, len(position), 2), dtype=np.float32)
    weight = np.zeros((_STEPS, len(position)), dtype=np.float32)
    history[0] = position
    distance = np.zeros(len(position), dtype=np.float32)
    lag_total = np.zeros(3, dtype=np.float64)
    active_count = np.zeros(3, dtype=np.int64)
    alive = np.ones(len(position), dtype=bool)
    for step in range(_STEPS):
        progress = step * (len(fields) - 1) / _STEPS
        index = min(int(progress), len(fields) - 2)
        fraction = progress - index
        fraction = fraction * fraction * (3 - 2 * fraction)
        target = ((1 - fraction) * _sample(fields[index], position)
                  + fraction * _sample(fields[index + 1], position))
        velocity = _relax_velocity(velocity, target, response, _DT)
        active = (step < lifetime) & alive
        previous = position
        position, escaped = _advance_particles(position, velocity, active, _DT)
        alive[escaped] = False
        active &= ~escaped
        displacement = position - previous
        distance += np.linalg.norm(displacement, axis=1)
        history[step + 1] = position
        age = np.clip((step + 0.5) / lifetime, 0, 1)
        envelope = np.maximum(0, np.sin(math.pi * age)) ** 0.72
        weight[step] = strength * envelope * active
        lag = np.linalg.norm(target - velocity, axis=1) * active
        lag_total += lag.reshape(3, count).sum(axis=1)
        active_count += active.reshape(3, count).sum(axis=1)
    endpoint = history[-1].reshape(3, count, 2)
    means = (lag_total / np.maximum(active_count, 1)).tolist()
    metadata = {
        "study": "inertial_filaments", "seed": int(seed), "controls": cfg,
        "program": program, "steps": _STEPS, "dt": _DT,
        "particles_per_cohort": count, "response_times": times.tolist(),
        "response_time_ranges": np.column_stack((response.reshape(3, count).min(axis=1),
                                                  response.reshape(3, count).max(axis=1))).tolist(),
        "mean_velocity_lag_by_cohort": means,
        "mean_distance_by_cohort": distance.reshape(3, count).mean(axis=1).tolist(),
        "endpoint_separation_from_fast": np.linalg.norm(endpoint - endpoint[0], axis=2).mean(axis=1).tolist(),
        "trajectory_sha256": hashlib.sha256(history.tobytes()).hexdigest(),
        "escaped_particle_count": int(np.count_nonzero(~alive)),
        "texture": "inertial transport, unequal particle strengths and finite lifetimes",
        "tint": [205, 225, 255], "background": [0, 0, 0],
    }
    return history, weight, metadata


def _density(history: np.ndarray, weight: np.ndarray, width: int, height: int) -> np.ndarray:
    lo, hi = history.min(axis=(0, 1)), history.max(axis=(0, 1))
    center = (lo + hi) * 0.5
    span = np.maximum(hi - lo, 0.2)
    scale = min((width - 1) / span[0], (height - 1) / span[1]) * 0.87
    density = np.zeros((height, width), dtype=np.float32)
    # Rasterize actual trajectory segments. More pixels increase sampling only;
    # neither integration nor the launch arrangement changes with image size.
    start = (history[:-1] - center) * scale + np.array(((width - 1) / 2, (height - 1) / 2))
    delta = (history[1:] - history[:-1]) * scale
    lengths = np.linalg.norm(delta, axis=2)
    subdivisions = np.maximum(1, np.ceil(lengths / 0.75).astype(np.int32))
    for index in range(int(subdivisions.max())):
        valid = (index < subdivisions) & (weight > 0)
        count = subdivisions[valid]
        p = start[valid] + delta[valid] * ((index + 0.5) / count)[:, None]
        splat(density, p[:, 0], p[:, 1], weight[valid] / count)
    return density


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, (int, np.integer))
            or not isinstance(height, (int, np.integer))
            or width < 64 or height < 64):
        raise ValueError("Study dimensions must be integers of at least 64 pixels")
    cfg = _settings(controls)
    history, weight, metadata = _simulate(seed, cfg)
    density = _density(history, weight, int(width), int(height))
    metadata["nonzero_density_pixels"] = int(np.count_nonzero(density))
    return density_image(density), metadata
