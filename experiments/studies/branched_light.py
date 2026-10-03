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

from .perlin_common import Perlin, splat
from .perlin_finish import finish_density, material_coordinate

TITLE = "Branched light"
DESCRIPTION = "Perlin refraction folds rays carrying coherent filament radiance and color into luminous caustics."
CONTROLS = {
    "refraction": {"default": 0.5, "label": "Refraction strength"},
    "distance": {"default": 0.5, "label": "Travel distance"},
    "finish": {"default": 1.0, "label": "Material finish"},
    "texture": {"default": 1.0, "label": "Light packets"},
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
    return scene


def _potential_value(scene, noise, x, y):
    c, s = math.cos(scene["field_angle"]), math.sin(scene["field_angle"])
    u, v = c * x - s * y, s * x + c * y
    ox, oy = scene["offset"]
    wx = u + scene["warp"] * noise.noise2(u * .8 + 37.1, v * .8 - 11.3)
    wy = v + scene["warp"] * noise.noise2(u * .8 - 7.6, v * .8 + 24.9)
    f = scene["frequency"]
    potential = noise.noise2(wx * f + ox, wy * f * scene["anisotropy"] + oy)
    potential += .18 * noise.noise2(wx * f * 2.3 - 13.4, wy * f * 2.3 + 5.7)
    return potential


class _Potential:
    """Lazily evaluate the same global Perlin lattice wherever rays travel."""

    spacing = 2.7 / 543
    cells = 512

    def __init__(self, scene):
        self.scene = scene
        self.noise = Perlin(scene["perlin_seed"])
        self.tiles = {}
        self.sample_count = 0
        self.value_sum = 0.0
        self.square_sum = 0.0
        self.exterior_samples = 0

    def _tile(self, tx, ty):
        key = (int(tx), int(ty))
        if key not in self.tiles:
            # A one-cell halo makes central differences identical on either
            # side of a tile seam; only interior gradients are interpolated.
            axis = np.arange(-1, self.cells + 2)
            x, y = np.meshgrid((tx * self.cells + axis) * self.spacing,
                               (ty * self.cells + axis) * self.spacing)
            potential = _potential_value(self.scene, self.noise, x, y)
            gy, gx = np.gradient(potential, self.spacing, self.spacing)
            self.tiles[key] = np.asarray([gx[1:-1, 1:-1], gy[1:-1, 1:-1]])
            self.sample_count += potential.size
            self.value_sum += float(potential.sum())
            self.square_sum += float(np.square(potential).sum())
        return self.tiles[key]

    def force(self, position, strength):
        if not np.isfinite(position).all():
            raise RuntimeError("Ray position must remain finite")
        grid_position = position / self.spacing
        tile_index = np.floor(grid_position / self.cells).astype(np.int64)
        local = grid_position - tile_index * self.cells
        outside = np.any((local < 0) | (local > self.cells), axis=1)
        self.exterior_samples += int(outside.sum())
        if np.any(outside):
            raise RuntimeError("Ray force sampled outside its evaluated Perlin tile")
        # Group the small number of visited tiles without sorting two columns.
        low = tile_index.min(axis=0)
        columns = int(tile_index[:, 0].max() - low[0] + 1)
        keys = (tile_index[:, 1] - low[1]) * columns + tile_index[:, 0] - low[0]
        result = np.empty_like(position)
        for key in np.unique(keys):
            mask = keys == key
            tx, ty = int(key % columns + low[0]), int(key // columns + low[1])
            gradient = self._tile(tx, ty)
            coordinates = local[mask, ::-1].T
            # Constant/NaN intentionally fails if interpolation ever escapes.
            result[mask] = -strength * np.stack([
                map_coordinates(g, coordinates, order=1, mode="constant", cval=np.nan, prefilter=False)
                for g in gradient], axis=1)
        if not np.isfinite(result).all():
            raise RuntimeError("Non-finite Perlin force interpolation")
        return result

    def metadata(self):
        indices = np.asarray(list(self.tiles))
        low = indices.min(axis=0) * self.cells * self.spacing
        high = (indices.max(axis=0) + 1) * self.cells * self.spacing
        variance = self.square_sum / self.sample_count - (self.value_sum / self.sample_count)**2
        return {
            "potential_grid": [self.cells + 3, self.cells + 3],
            "potential_sampling_spacing": self.spacing,
            "potential_tile_count": len(self.tiles),
            "potential_bounds": [float(low[0]), float(high[0]), float(low[1]), float(high[1])],
            "potential_standard_deviation": math.sqrt(max(0.0, variance)),
            "potential_exterior_samples": self.exterior_samples,
        }


def _packet_multiplier(rng, noise, coordinate, age, probability, texture):
    selected = rng.random(len(age)) < probability
    # This emission pattern lives in launch-coordinate / travel-time space.
    # The selected positions still lie on the fully integrated ray paths.
    modulation = noise.noise2(coordinate[selected] * 48.0 + 3.17,
                              age[selected] * 23.0 + 7.91)
    envelope = 1 + texture * (1.76 * np.clip(.5 + 1.75 * modulation, 0, 1) - .88)
    return selected, envelope / probability


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 64 or height < 64:
        raise ValueError("Images must be at least 64 pixels on each side")
    cfg = _controls(controls)
    scene = _scene(int(seed))
    aspect = width / height
    potential = _Potential(scene)
    strength = .85 * cfg["refraction"]
    distance = 1.1 + 2.0 * cfg["distance"]
    ds = .0027
    positions, momenta, lifetimes, weights, materials, source_coordinates = [], [], [], [], [], []
    count_per_launch = 4608
    radiance_noise = Perlin(int(seed) + 87371)
    radiance_samples = []
    for launch_index, launch in enumerate(scene["launches"]):
        t = np.linspace(-.5, .5, count_per_launch)
        direction = np.array([math.cos(launch["angle"]), math.sin(launch["angle"])])
        tangent = np.array([-direction[1], direction[0]])
        center = np.asarray(launch["center"]) * np.array([aspect, 1])
        transverse = t * launch["width"]
        initial = (center + transverse[:, None] * tangent +
                   (launch["bend"] * transverse**2)[:, None] * direction)
        positions.append(initial)
        # A curved initial wavefront launches along its local normal.
        p = direction - (2 * launch["bend"] * transverse)[:, None] * tangent
        p /= np.linalg.norm(p, axis=1, keepdims=True)
        momenta.append(p)
        lifetimes.append(np.full(count_per_launch, distance * launch["distance_ratio"]))
        # Neighboring rays carry coherent, unequal launch radiance throughout
        # transport. Fine variations consequently stretch along actual paths.
        coarse = radiance_noise.noise2(transverse * 5.7 + 11.1, launch_index * 3.17 + .43)
        fine = radiance_noise.noise2(transverse * 92.0 + 7.3, launch_index * 7.91 + .71)
        micro = radiance_noise.noise2(transverse * 237.0 - 19.7, launch_index * 5.63 + .29)
        radiance = (.38 + np.clip(.5 + 1.35 * coarse, 0, 1))
        radiance *= .10 + 1.9 * np.clip(.48 + 1.8 * fine, 0, 1)**2
        radiance *= .70 + .60 * np.clip(.5 + 1.5 * micro, 0, 1)
        radiance_samples.append(radiance)
        weights.append((np.cos(t * math.pi)**2) * launch["weight"] * launch["width"] / count_per_launch * radiance)
        materials.append(material_coordinate(int(seed), initial[:, 0] * 1.7, initial[:, 1] * 1.7))
        source_coordinates.append(transverse + launch_index * 17.13)
    position = np.concatenate(positions)
    momentum = np.concatenate(momenta)
    lifetime = np.concatenate(lifetimes)
    weight = np.concatenate(weights)
    material = np.concatenate(materials)
    source_coordinate = np.concatenate(source_coordinates)
    initial_position, initial_momentum = position.copy(), momentum.copy()
    age = np.zeros(len(position))
    sampling_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 19873]))
    first_step = sampling_rng.uniform(.05 * ds, ds, len(position))
    acceleration = potential.force(position, strength)
    maximum_steps = int(math.ceil(float(lifetime.max()) / ds))
    # Controls and launch limits bound this buffer at 1355 * 18432 * 2 * 4
    # bytes (191 MiB), independent of output resolution or aspect ratio.
    trajectory = np.empty((maximum_steps, len(position), 2), dtype=np.float32)
    world_min, world_max = np.full(2, np.inf), np.full(2, -np.inf)
    active = np.ones(len(position), dtype=bool)
    for step in range(maximum_steps):
        # Velocity Verlet; forces bend momentum, they do not prescribe velocity.
        # Stagger the initial sample times to avoid coherent raster bands.
        dt = first_step[active] if step == 0 else np.full(int(active.sum()), ds)
        momentum[active] += .5 * dt[:, None] * acceleration[active]
        position[active] += dt[:, None] * momentum[active]
        age[active] += dt
        acceleration[active] = potential.force(position[active], strength)
        momentum[active] += .5 * dt[:, None] * acceleration[active]
        trajectory[step] = position
        active &= age < lifetime
        if np.any(active):
            world_min = np.minimum(world_min, position[active].min(axis=0))
            world_max = np.maximum(world_max, position[active].max(axis=0))
        if not active.any():
            break
    steps = step + 1
    # Fit every deposited ray, preserving aspect and an 8% margin on each side.
    # Fixed world structure and transport remain independent of pixel count.
    center = (world_min + world_max) * .5
    span = np.maximum(world_max - world_min, .1) * 1.19
    span[0] = max(span[0], span[1] * aspect)
    span[1] = span[0] / aspect
    camera_min = center - span * .5
    camera_max = center + span * .5
    density = np.zeros((height, width), dtype=np.float64)
    color_density = np.zeros_like(density)
    candidates = int(np.minimum(steps, np.ceil((lifetime - first_step) / ds)).sum())
    packet_target = 90000
    probability = float(np.clip(packet_target / candidates, .003, .025)) ** cfg["texture"]
    packet_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 53719]))
    packet_noise_seed = int(np.random.default_rng(np.random.SeedSequence([int(seed), 64283])).integers(2**31))
    packet_noise = Perlin(packet_noise_seed)
    continuous_fraction = .12 * cfg["texture"] if cfg["texture"] > 0 else 1.0
    samples, packets = 0, 0
    for begin in range(0, steps, 24):
        end = min(steps, begin + 24)
        sample_age = first_step[None, :] + np.arange(begin, end)[:, None] * ds
        visible = sample_age < lifetime[None, :]
        points = trajectory[begin:end][visible]
        fade = np.minimum(1, (lifetime[None, :] - sample_age) / .18)
        fade *= np.minimum(1, sample_age / .28)**2
        radiance = (weight[None, :] * fade * ds)[visible]
        color_radiance = (weight[None, :] * fade * ds * material[None, :])[visible]
        samples += len(points)
        if cfg["texture"] > 0:
            # A faint continuous deposit keeps the caustic seams connected;
            # most light is emitted by sparse, irregular packets below.
            px = (points[:, 0] - camera_min[0]) / span[0] * (width - 1)
            py = (points[:, 1] - camera_min[1]) / span[1] * (height - 1)
            splat(density, px, py, radiance * continuous_fraction)
            splat(color_density, px, py, color_radiance * continuous_fraction)
            coordinate = np.broadcast_to(source_coordinate, sample_age.shape)[visible]
            selected, multiplier = _packet_multiplier(packet_rng, packet_noise, coordinate,
                                                       sample_age[visible], probability, cfg["texture"])
            points = points[selected]
            radiance = radiance[selected] * multiplier * (1 - continuous_fraction)
            color_radiance = color_radiance[selected] * multiplier * (1 - continuous_fraction)
        px = (points[:, 0] - camera_min[0]) / span[0] * (width - 1)
        py = (points[:, 1] - camera_min[1]) / span[1] * (height - 1)
        splat(density, px, py, radiance)
        splat(color_density, px, py, color_radiance)
        packets += len(points)
    nonzero = density[density > 0]
    exposure = float(np.quantile(nonzero, .992)) if len(nonzero) else 1.0
    image, finish_meta = finish_density(density, int(seed), color_density=color_density,
                                       exposure=exposure, strength=cfg["finish"], grain=.06,
                                       bloom=.10 - .07 * cfg["texture"], detail=.20)
    ballistic = initial_position + initial_momentum * age[:, None]
    displacement = np.linalg.norm(position - ballistic, axis=1)
    return image, {
        "algorithm": "Hamiltonian ray focusing in a warped Perlin potential; velocity Verlet; bilinear radiance accumulation",
        "seed": int(seed), "width": width, "height": height, "controls": cfg,
        "scene": scene, **potential.metadata(),
        "potential_strength": strength, "integration_step": ds,
        "sample_phase": "seeded first-step offsets in [0.05*ds, ds]; then constant ds",
        "integration_steps": steps, "ray_count": len(position), "ray_samples_in_frame": samples,
        "deposition": {"packet_count": packets, "target_packets": packet_target,
                       "continuous_radiance_fraction": continuous_fraction,
                       "retention_probability": probability, "perlin_seed": packet_noise_seed,
                       "rng_stream": 53719, "source_frequency": 48.0, "time_frequency": 23.0,
                       "mechanism": ("independent sparse trajectory samples with inverse-probability weights and Perlin emission modulation"
                                     if cfg["texture"] > 0 else "continuous ray deposition")},
        "launch_material": {"radiance_perlin_seed": int(seed) + 87371,
                            "frequencies": [5.7, 92.0, 237.0], "transport": "constant radiance and color coordinate carried by each ray",
                            "radiance_minimum": float(np.min(radiance_samples)),
                            "radiance_maximum": float(np.max(radiance_samples))},
        "camera_bounds": [camera_min.tolist(), camera_max.tolist()],
        "deposited_world_bounds": [world_min.tolist(), world_max.tolist()],
        "trajectory_capacity_bytes": int(trajectory.nbytes),
        "travel_distance": distance, "density_exposure": exposure,
        "density_sum": float(density.sum()),
        "density_maximum": float(density.max()), "nonzero_pixels": int(len(nonzero)),
        "mean_displacement_from_ballistic": float(displacement.mean()),
        "maximum_displacement_from_ballistic": float(displacement.max()),
        "mean_momentum_change": float(np.linalg.norm(momentum - initial_momentum, axis=1).mean()),
        "background": [0, 0, 0], "finish": finish_meta,
    }
