"""Perlin currents traced by particles with distinct velocity response times.

The field construction uses the curl of a smooth noise potential, following
Bridson, Hourihan and Nordenstam, Curl-Noise for Procedural Fluid Flow (2007):
https://www.cs.ubc.ca/~rbridson/docs/bridson-siggraph2007-curlnoise.pdf
The particles instead retain velocity: dv/dt = (flow(position, time)-v)/tau.
This is an artistic inertial-tracer model, not a fluid or light simulation.
Wide, unequal particle curtains carry continuous variations in response time
and material through the flow. Sparse, compensated light packets give their
deposits irregular material texture. Packet emission follows an independent
seeded stream and coherent source/arclength Perlin modulation. The optional
shared finish colors the density without changing the world-space simulation.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.ndimage import map_coordinates

from experiments.studies.perlin_common import Perlin, splat
from experiments.studies.perlin_finish import finish_density, material_coordinate

TITLE = "Inertial filaments"
DESCRIPTION = "Unequal particle curtains stretch into textured luminous areas and fine strands in changing Perlin currents."
CONTROLS = {
    "inertia": {"default": 0.5, "label": "Momentum separation"},
    "turbulence": {"default": 0.5, "label": "Fine currents"},
    "texture": {"default": 1.0, "label": "Granular material"},
    "finish": {"default": 1.0, "label": "Color and material finish"},
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
    curtain_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 68117]))
    count = int(rng.integers(2, 6))
    emitters = []
    for _ in range(count):
        emitters.append({
            "center": rng.uniform(-1.05, 1.05, 2).tolist(),
            "angle": float(rng.uniform(-math.pi, math.pi)),
            "length": float(rng.uniform(0.7, 1.75)),
            "bend": float(rng.uniform(-0.7, 0.7)),
            "bundles": int(rng.integers(3, 7)),
            "kick": rng.uniform(-0.12, 0.12, 2).tolist(),
            "width": float(curtain_rng.uniform(0.12, 0.46)),
            "source_phase": curtain_rng.uniform(-40, 40, 2).tolist(),
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
    noise = Perlin(seed)
    origins, kicks, strengths = [], [], []
    for emitter in program["emitters"]:
        center = np.asarray(emitter["center"])
        cs, sn = math.cos(emitter["angle"]), math.sin(emitter["angle"])
        tangent, normal = np.array((cs, sn)), np.array((-sn, cs))
        # Stratified samples cover a coherent source area rather than repeated
        # identical lines. Perlin changes its width, curvature and dye density.
        nu, nv = 48 + emitter["bundles"] * 4, int(rng.integers(9, 14))
        iy, ix = np.mgrid[:nv, :nu]
        along = ((ix + rng.random(ix.shape)) / nu - 0.5).ravel()
        across = (2 * (iy + rng.random(iy.shape)) / nv - 1).ravel()
        ox, oy = emitter["source_phase"]
        broad = noise.noise2(along * 3.1 + ox, oy)
        width = emitter["width"] * (0.78 + 0.5 * broad)
        curve = emitter["length"] * (emitter["bend"] * along ** 2 + 0.18 * broad)
        points = (center + (along * emitter["length"])[:, None] * tangent
                  + (curve + across * width)[:, None] * normal)
        density = np.clip(0.58 + 1.25 * noise.noise2(along * 5.0 + ox,
                                                  across * 1.5 + oy), 0.02, 1.2) ** 1.6
        edge = np.maximum(0, 1 - across ** 2) ** 0.8 * np.maximum(0, 1 - (along * 2) ** 2) ** 0.5
        count = len(points)
        origins.append(points)
        kicks.append(np.tile(emitter["kick"], (count, 1)))
        strengths.append(density * edge * rng.lognormal(-0.1, 0.28, count)
                         * rng.uniform(0.65, 1.35))
    origin = np.concatenate(origins).astype(np.float32)
    kick = np.concatenate(kicks).astype(np.float32)
    strength = np.concatenate(strengths).astype(np.float32)
    # All three cohorts start identically: later separation is caused by inertia.
    times = np.array((0.025, 0.11 + cfg["inertia"] * 0.32,
                      0.28 + cfg["inertia"] * 1.3), dtype=np.float32)
    count = len(origin)
    # Response times vary continuously, both coherently across each curtain and
    # between nearby particles. The resulting fans are simulated, not blurred.
    response_spread = np.clip(np.exp(1.15 * noise.noise2(origin[:, 0] * 2.8 + 17.3,
                                                       origin[:, 1] * 2.8 - 28.1)
                                    + rng.normal(0, 0.13, count)), 0.42, 1.95).astype(np.float32)
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


def _boundary_weight(position: np.ndarray) -> np.ndarray:
    distance = _DOMAIN - np.abs(position).max(axis=1)
    fade = np.clip(distance / 0.8, 0, 1)
    return fade * fade * (3 - 2 * fade)


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
        weight[step] = strength * envelope * active * _boundary_weight(position)
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
        "launch_extent": (history[0].max(axis=0) - history[0].min(axis=0)).tolist(),
        "texture": "Perlin-modulated particle curtains and continuous inertial transport",
        "background": [0, 0, 0],
    }
    return history, weight, metadata


def _density(history: np.ndarray, weight: np.ndarray, width: int, height: int,
             material: np.ndarray):
    lo, hi = history.min(axis=(0, 1)), history.max(axis=(0, 1))
    center = (lo + hi) * 0.5
    span = np.maximum(hi - lo, 0.2)
    scale = min((width - 1) / span[0], (height - 1) / span[1]) * 0.87
    density = np.zeros((height, width), dtype=np.float32)
    color_density = np.zeros_like(density)
    # Rasterize actual trajectory segments. More pixels increase sampling only;
    # neither integration nor the launch arrangement changes with image size.
    # Chunked deposition bounds temporary memory as the curtains grow denser.
    for first in range(0, len(weight), 48):
        last = min(first + 48, len(weight))
        delta_world = history[first + 1:last + 1] - history[first:last]
        start = ((history[first:last] - center) * scale
                 + np.array(((width - 1) / 2, (height - 1) / 2)))
        delta = delta_world * scale
        lengths = np.linalg.norm(delta, axis=2)
        subdivisions = np.maximum(1, np.ceil(lengths / 0.75).astype(np.int32))
        # The material coordinate is carried from the source. A small speed
        # component relates color to local motion without recoloring geometry.
        coordinate = np.clip(0.88 * material[None, :]
                             + 0.12 * np.linalg.norm(delta_world, axis=2) / (_DT * 0.65), 0, 1)
        local_weight = weight[first:last]
        for index in range(int(subdivisions.max())):
            valid = (index < subdivisions) & (local_weight > 0)
            count = subdivisions[valid]
            p = start[valid] + delta[valid] * ((index + 0.5) / count)[:, None]
            amount = local_weight[valid] / count
            splat(density, p[:, 0], p[:, 1], amount)
            splat(color_density, p[:, 0], p[:, 1], amount * coordinate[valid])
    return density, color_density


def _packet_weights(history: np.ndarray, weight: np.ndarray, seed: int,
                    strength: float):
    """Thin material emission in world space, preserving local light in expectation.

    Sampling and probability compensation happen before rasterization. The
    packet budget does not depend on image size, finishing or the flow's RNG.
    A small continuous deposit retains the faintest connections between packets.
    """
    if strength == 0:
        return weight, {"strength": 0.0, "emitted_packets": 0,
                        "continuous_fraction": 1.0,
                        "weight_sha256": hashlib.sha256(weight.tobytes()).hexdigest()}
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 91373]))
    noise = Perlin(int(np.random.default_rng(np.random.SeedSequence([int(seed), 94811])).integers(2**31)))
    # Approximately 70% of the finite-lifetime samples are active. Use the fixed
    # sample count here so changing one cohort cannot reroll another's packets.
    probability = min(0.25, 100000.0 / max(weight.size * 0.7, 1))
    continuous = 0.12
    output = np.empty_like(weight)
    travelled = np.zeros(weight.shape[1], dtype=np.float32)
    origin = history[0]
    source_u = noise.noise2(origin[:, 0] * 2.2 + 12.7,
                           origin[:, 1] * 2.2 - 6.3) * 3.4
    source_v = origin[:, 0] * 4.1 + origin[:, 1] * 3.7 - 27.3
    emitted = 0
    for first in range(0, len(weight), 48):
        last = min(first + 48, len(weight))
        displacement = history[first + 1:last + 1] - history[first:last]
        distance = np.cumsum(np.linalg.norm(displacement, axis=2), axis=0) + travelled
        travelled = distance[-1].copy()
        # Nonperiodic patches of fine and coarse packets move with each source's
        # material coordinate and accumulate along its actual travelled distance.
        modulation = noise.noise2(source_u[None, :] + distance * 7.5,
                                 source_v[None, :])
        chance = probability * np.clip(0.78 + 1.25 * modulation, 0.35, 1.8)
        selected = rng.random(chance.shape) < chance
        local = weight[first:last]
        emitted += int(np.count_nonzero(selected & (local > 0)))
        compensated = selected / chance
        multiplier = ((1 - strength) + strength * continuous
                      + strength * (1 - continuous) * compensated)
        output[first:last] = local * multiplier
    return output, {"strength": float(strength), "emitted_packets": emitted,
                    "target_packets": 100000, "base_probability": float(probability),
                    "continuous_fraction": float(1 - strength * (1 - continuous)),
                    "expected_light_compensated": True,
                    "weight_sha256": hashlib.sha256(output.tobytes()).hexdigest()}


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, (int, np.integer))
            or not isinstance(height, (int, np.integer))
            or width < 64 or height < 64):
        raise ValueError("Study dimensions must be integers of at least 64 pixels")
    cfg = _settings(controls)
    history, weight, metadata = _simulate(seed, cfg)
    weight, metadata["packet_deposition"] = _packet_weights(history, weight, seed, cfg["texture"])
    material = material_coordinate(seed, history[0, :, 0], history[0, :, 1])
    density, color_density = _density(history, weight, int(width), int(height), material)
    metadata["nonzero_density_pixels"] = int(np.count_nonzero(density))
    metadata["density_sha256"] = hashlib.sha256(density.tobytes()).hexdigest()
    metadata["material_sha256"] = hashlib.sha256(color_density.tobytes()).hexdigest()
    result, finish = finish_density(density, seed, color_density=color_density,
                                    strength=cfg["finish"], bloom=0.10 - 0.07 * cfg["texture"])
    metadata["finish"] = finish
    return result, metadata
