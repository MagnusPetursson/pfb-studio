"""Competitive space colonization in irregular, obstructed attraction domains.

Primary source: Runions, Lane and Prusinkiewicz, Modeling Trees with a Space
Colonization Algorithm (2007):
https://algorithmicbotany.org/papers/colonization.egwnp2007.pdf
Attraction sites choose their nearest branch node; nodes extend toward their
assigned sites, then consume nearby sites. This study varies domains, roots,
voids and tropism. Rendering uses descendant mass for tapered branching.
It produces trees/forests (no graph cycles), not a biological growth model.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

TITLE = "Branching ecologies"
DESCRIPTION = "Competing branching colonies consume irregular attraction domains, bending around open voids."
CONTROLS = {
    "density": {"default": 0.5, "label": "Branch density"},
    "reach": {"default": 0.5, "label": "Attraction reach"},
    "tropism": {"default": 0.5, "label": "Directional growth"},
    "taper": {"default": 0.5, "label": "Branch taper"},
}


def _controls(values):
    supplied = values or {}
    unknown = set(supplied) - set(CONTROLS)
    if unknown:
        raise ValueError(f"Unknown ecology controls: {sorted(unknown)}")
    result = {k: float(supplied.get(k, v["default"])) for k, v in CONTROLS.items()}
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in result.values()):
        raise ValueError("Ecology controls must be finite values in [0, 1]")
    return result


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 1 or height < 1:
        raise ValueError("Image dimensions must be positive")
    c = _controls(controls)
    rng = np.random.default_rng(seed)
    extent = np.array([width, height], dtype=float) / min(width, height)
    angle = rng.uniform(-math.pi, math.pi)
    axis = np.array([math.cos(angle), math.sin(angle)])
    cross = np.array([-axis[1], axis[0]])
    domain_count = int(rng.integers(2, 6))
    domain_centers, domain_axes, domain_rotations = [], [], []
    for i in range(domain_count):
        along = (i / max(domain_count - 1, 1) - 0.5) * rng.uniform(0.36, 0.64)
        center = extent / 2 + axis * along + cross * rng.uniform(-0.17, 0.17)
        domain_centers.append(center)
        domain_axes.append(rng.uniform([0.12, 0.11], [0.29, 0.23]))
        a = angle + rng.uniform(-1.2, 1.2)
        domain_rotations.append(np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]))
    obstacle_count = int(rng.integers(1, 4))
    obstacle_centers = extent / 2 + rng.uniform(-0.24, 0.24, (obstacle_count, 2))
    obstacle_radii = rng.uniform(0.040, 0.093, obstacle_count)

    def valid(points):
        good = ((points > 0.055) & (points < extent - 0.055)).all(axis=1)
        for center, radius in zip(obstacle_centers, obstacle_radii):
            good &= np.linalg.norm(points - center, axis=1) > radius
        return good

    def segment_clearance(starts, ends):
        # Exact segment-to-circle clearance prevents a tangential chord from
        # cutting through a void even when both endpoints are outside it.
        direction = ends - starts
        squared_length = np.maximum(np.sum(direction * direction, axis=1), 1e-20)
        clearance = np.full(len(starts), np.inf)
        for center, radius in zip(obstacle_centers, obstacle_radii):
            t = np.clip(np.sum((center - starts) * direction, axis=1) / squared_length, 0, 1)
            closest = starts + direction * t[:, None]
            clearance = np.minimum(clearance, np.linalg.norm(closest - center, axis=1) - radius)
        return clearance

    # Overlapping anisotropic lobes make an irregular domain; angular waves
    # alter its boundary without imposing radial symmetry on the composition.
    target_sites = int(7000 + 12000 * c["density"])
    # A fixed-size reference cloud scouts root locations. Its fixed RNG work
    # preserves the existing default compositions while making layout and
    # palette independent of how many attraction sites density requests.
    reference_sites = 13000
    domain_phases = []
    chunks = []
    for center, axes, rotation in zip(domain_centers, domain_axes, domain_rotations):
        n = int(reference_sites / domain_count * 1.35)
        theta = rng.uniform(0, 2 * math.pi, n)
        phase = rng.uniform(0, 2 * math.pi, 2)
        domain_phases.append(phase)
        edge = 1 + 0.17 * np.sin(3 * theta + phase[0]) + 0.13 * np.sin(5 * theta + phase[1])
        radius = np.sqrt(rng.uniform(0, 1, n)) * edge
        sites = np.column_stack([np.cos(theta), np.sin(theta)]) * radius[:, None] * axes
        sites = sites @ rotation.T + center
        chunks.append(sites[valid(sites)])
    sites = np.concatenate(chunks)
    if len(sites) > reference_sites:
        sites = sites[rng.choice(len(sites), reference_sites, replace=False)]
    if not len(sites):
        raise RuntimeError("No attraction sites survived the domain constraints")
    root_count = int(rng.integers(2, 5))
    # Root locations follow different boundaries of the actual attraction
    # domain. They are not all placed beneath a predesigned upright crown.
    roots = []
    root_directions = []
    for i in range(root_count):
        a = angle + rng.uniform(-1.4, 1.4) + (math.pi if i % 2 else 0)
        direction = np.array([math.cos(a), math.sin(a)])
        projection = sites @ direction
        candidates = np.flatnonzero(projection < np.quantile(projection, 0.08))
        chosen = sites[int(rng.choice(candidates))]
        if roots:
            candidates = candidates[np.linalg.norm(sites[candidates, None] - np.array(roots), axis=2).min(axis=1) > 0.045]
            if len(candidates):
                chosen = sites[int(rng.choice(candidates))]
        roots.append(chosen)
        root_directions.append(direction)
    if target_sites != reference_sites:
        # Density changes sampling and the consumption radius, never the
        # selected domain boundary, roots, growth directions, or palette.
        sampling_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 6179]))
        chunks = []
        for center, axes, rotation, phase in zip(domain_centers, domain_axes, domain_rotations, domain_phases):
            n = int(target_sites / domain_count * 1.35)
            theta = sampling_rng.uniform(0, 2 * math.pi, n)
            edge = 1 + 0.17 * np.sin(3 * theta + phase[0]) + 0.13 * np.sin(5 * theta + phase[1])
            radius = np.sqrt(sampling_rng.uniform(0, 1, n)) * edge
            sampled = np.column_stack([np.cos(theta), np.sin(theta)]) * radius[:, None] * axes
            sampled = sampled @ rotation.T + center
            chunks.append(sampled[valid(sampled)])
        sites = np.concatenate(chunks)
        if len(sites) > target_sites:
            sites = sites[sampling_rng.choice(len(sites), target_sites, replace=False)]
        if not len(sites):
            raise RuntimeError("No attraction sites survived the domain constraints")
    initial_sites = len(sites)
    initial_site_bounds = [sites.min(axis=0).tolist(), sites.max(axis=0).tolist()]
    nodes = np.array(roots)
    parents = np.full(root_count, -1, dtype=int)
    colony = np.arange(root_count, dtype=int)
    depth = np.zeros(root_count, dtype=int)
    heading = np.array(root_directions)
    step_length = 0.0058
    kill_distance = 0.0058 + 0.003 * (1 - c["density"])
    influence = 0.075 + 0.18 * c["reach"]
    max_nodes = 14000
    max_steps = 230
    iterations = 0
    consumed = 0
    blocked_proposals = 0
    for iteration in range(max_steps):
        iterations = iteration + 1
        tree = cKDTree(nodes)
        distance, nearest = tree.query(sites, k=1)
        alive = distance > kill_distance
        consumed += int(np.count_nonzero(~alive))
        sites, distance, nearest = sites[alive], distance[alive], nearest[alive]
        if not len(sites):
            break
        influenced = distance < influence
        if not influenced.any():
            break
        owners = nearest[influenced]
        attraction = _unit(sites[influenced] - nodes[owners])
        sums = np.zeros_like(nodes)
        np.add.at(sums, owners, attraction)
        counts = np.bincount(owners, minlength=len(nodes))
        growing = np.flatnonzero(counts)
        directions = sums[growing] / counts[growing, None]
        # Parent heading encourages branching continuity, not one fixed axis.
        directions += heading[growing] * (0.1 + 0.30 * c["tropism"])
        directions += np.array(root_directions)[colony[growing]] * (0.06 * c["tropism"])
        directions = _unit(directions)
        proposals = nodes[growing] + directions * step_length
        legal = valid(proposals) & (segment_clearance(nodes[growing], proposals) > 0)
        # A rejected branch does not consume sites; another colony may reach
        # them from the far side. Close duplicate children would stall growth.
        separation, _ = tree.query(proposals, k=1)
        legal &= separation > step_length * 0.65
        blocked_proposals += int(np.count_nonzero(~legal))
        growing, proposals, directions = growing[legal], proposals[legal], directions[legal]
        room = max_nodes - len(nodes)
        growing, proposals, directions = growing[:room], proposals[:room], directions[:room]
        if not len(growing):
            break
        # Children proposed in this same step also require separation.
        near = cKDTree(proposals).query_pairs(step_length * 0.55, output_type="ndarray")
        keep = np.ones(len(proposals), dtype=bool)
        for a, b in near:
            if keep[a]:
                keep[b] = False
        growing, proposals, directions = growing[keep], proposals[keep], directions[keep]
        nodes = np.concatenate([nodes, proposals])
        parents = np.concatenate([parents, growing])
        colony = np.concatenate([colony, colony[growing]])
        depth = np.concatenate([depth, depth[growing] + 1])
        heading = np.concatenate([heading, directions])
        if len(nodes) >= max_nodes:
            break

    mass = np.ones(len(nodes), dtype=float)
    for i in range(len(nodes) - 1, root_count - 1, -1):
        mass[parents[i]] += mass[i]
    # Descendant mass supplies gradual taper independent of drawing order.
    thick = 0.50 + np.power(mass, 0.40 + 0.13 * c["taper"]) * 0.20
    thick = np.minimum(thick, 6.0)
    palettes = [((239, 234, 221), (31, 62, 71), (178, 75, 38)),
                ((227, 232, 221), (25, 64, 51), (149, 79, 42)),
                ((238, 227, 215), (66, 54, 80), (163, 63, 49)),
                ((229, 233, 232), (27, 63, 93), (173, 100, 36))]
    paper, ink, accent = palettes[int(rng.integers(len(palettes)))]
    scale = 2
    image = Image.new("RGB", (width * scale, height * scale), paper)
    draw = ImageDraw.Draw(image, "RGBA")
    px = min(width, height) * scale
    maximum_depth = max(int(depth.max()), 1)
    # Subtle attraction-site remnants expose the territory still available.
    # They are bounded, visually subordinate, and use the actual final sites.
    for point in sites[::max(1, len(sites) // 1100)]:
        x, y = point * px
        draw.ellipse((x - 0.6, y - 0.6, x + 0.6, y + 0.6), fill=(*ink, 27))
    order = np.argsort(-mass, kind="stable")
    for i in order:
        parent = parents[i]
        if parent < 0:
            continue
        start, finish = nodes[parent] * px, nodes[i] * px
        delta = finish - start
        normal = np.array([-delta[1], delta[0]]) / max(np.linalg.norm(delta), 1e-12)
        t = depth[i] / maximum_depth
        mix = np.clip(0.05 + 0.42 * t + 0.36 * (colony[i] % 3 == 1), 0, 1)
        color = tuple(int(a * (1 - mix) + b * mix) for a, b in zip(ink, accent))
        w0 = thick[parent] * px / 1024 / 2
        w1 = thick[i] * px / 1024 / 2
        polygon = [tuple(start + normal * w0), tuple(finish + normal * w1),
                   tuple(finish - normal * w1), tuple(start - normal * w0)]
        draw.polygon(polygon, fill=(*color, 220))
        # Rounded joints prevent gaps when branch direction changes sharply.
        draw.ellipse((finish[0] - w1, finish[1] - w1, finish[0] + w1, finish[1] + w1), fill=(*color, 220))
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    texture_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 1483]))
    noise = texture_rng.normal(0, 0.50, (height, width, 1))
    image = Image.fromarray(np.clip(np.asarray(image, dtype=float) + noise, 0, 255).astype(np.uint8))
    children = np.bincount(parents[parents >= 0], minlength=len(nodes))
    edge_nodes = np.arange(root_count, len(nodes))
    minimum_clearance = segment_clearance(nodes[parents[edge_nodes]], nodes[edge_nodes])
    return image, {
        "study": "ecologies", "seed": int(seed), "controls": c,
        "iterations": iterations, "root_count": root_count,
        "domain_lobes": domain_count, "obstacles": obstacle_count,
        "initial_sites": initial_sites, "consumed_sites": consumed,
        "remaining_sites": len(sites), "nodes": len(nodes),
        "branch_points": int(np.count_nonzero(children > 1)),
        "tips": int(np.count_nonzero(children == 0)), "max_depth": maximum_depth,
        "blocked_proposals": blocked_proposals, "node_limit": max_nodes,
        "edges": len(edge_nodes),
        "forest_valid": bool(np.all((parents[edge_nodes] >= 0) & (parents[edge_nodes] < edge_nodes))),
        "minimum_obstacle_clearance": float(minimum_clearance.min()) if len(minimum_clearance) else None,
        "initial_site_bounds": initial_site_bounds,
        "layout": {
            "domain_centers": np.array(domain_centers).tolist(),
            "domain_axes": np.array(domain_axes).tolist(),
            "domain_rotations": np.array(domain_rotations).tolist(),
            "domain_phases": np.array(domain_phases).tolist(),
            "obstacle_centers": obstacle_centers.tolist(),
            "obstacle_radii": obstacle_radii.tolist(),
            "roots": np.array(roots).tolist(),
            "root_directions": np.array(root_directions).tolist(),
        },
        "palette": {"paper": list(paper), "ink": list(ink), "accent": list(accent)},
        "finite_geometry": bool(np.isfinite(nodes).all()),
        "algorithm": "competitive nearest-node space colonization with cKDTree",
    }
