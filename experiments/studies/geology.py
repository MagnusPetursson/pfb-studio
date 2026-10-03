"""Geological print study: uplift, drainage incision, then stratified pigment.

Source basis: Red Blob Games' Mapgen4 (https://www.redblobgames.com/maps/mapgen4/)
separates large terrain design, drainage and presentation. This is an original,
simplified raster study, not a reproduction or a physically calibrated model.
Priority flooding supplies outlets; descending flow accumulation drives incision.
"""
from __future__ import annotations

import heapq
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, gaussian_filter1d, zoom
import contourpy

TITLE = "Geological prints"
DESCRIPTION = "Unequal uplifted ranges, eroded tributaries and mineral strata printed on paper."
CONTROLS = {
    "relief": {"default": 0.5, "label": "Range relief"},
    "incision": {"default": 0.5, "label": "Drainage incision"},
    "strata": {"default": 0.5, "label": "Stratum density"},
}


def _smooth(rng, shape, scale):
    small = rng.normal(size=(scale, scale))
    a = zoom(small, (shape[0] / scale, shape[1] / scale), order=3)[:shape[0], :shape[1]]
    return (a - a.mean()) / max(float(a.std()), 1e-9)


def _drain(h):
    """Fill pits, then route to a strictly lower neighbor (no drainage cycles)."""
    ny, nx = h.shape
    filled = h.copy()
    seen = np.zeros(h.shape, dtype=bool)
    queue = []
    for y, x in [(0, x) for x in range(nx)] + [(ny-1, x) for x in range(nx)] + [(y, 0) for y in range(1, ny-1)] + [(y, nx-1) for y in range(1, ny-1)]:
        seen[y, x] = True
        heapq.heappush(queue, (float(h[y, x]), y, x))
    directions = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    while queue:
        z, y, x = heapq.heappop(queue)
        for dy, dx in directions:
            yy, xx = y + dy, x + dx
            if 0 <= yy < ny and 0 <= xx < nx and not seen[yy, xx]:
                seen[yy, xx] = True
                zz = max(float(h[yy, xx]), z + 1e-6)
                filled[yy, xx] = zz
                heapq.heappush(queue, (zz, yy, xx))
    indexes = np.arange(ny * nx).reshape(h.shape)
    dest = indexes.copy()
    best = np.zeros_like(h)
    for dy, dx in directions:
        moved = np.roll(filled, (-dy, -dx), axis=(0, 1))
        slope = (filled - moved) / math.hypot(dx, dy)
        if dy < 0: slope[0] = 0
        if dy > 0: slope[-1] = 0
        if dx < 0: slope[:, 0] = 0
        if dx > 0: slope[:, -1] = 0
        take = slope > best
        best[take] = slope[take]
        dest[take] = np.roll(indexes, (-dy, -dx), axis=(0, 1))[take]
    flow = np.ones(ny * nx, dtype=np.float64)
    flat_dest = dest.ravel()
    for i in np.argsort(filled.ravel())[::-1]:
        j = flat_dest[i]
        if i != j:
            flow[j] += flow[i]
    return dest, flow.reshape(h.shape), filled


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 64 or height < 64:
        raise ValueError("Study dimensions must be at least 64 pixels")
    c = {k: v["default"] for k, v in CONTROLS.items()}
    c.update(controls or {})
    if any(k not in CONTROLS or not np.isfinite(v) or not 0 <= v <= 1 for k, v in c.items()):
        raise ValueError("Controls must be finite normalized values")
    rng = np.random.default_rng(seed)
    ny = max(96, round(280 * height / max(width, height)))
    nx = max(96, round(280 * width / max(width, height)))
    y, x = np.mgrid[0:ny, 0:nx].astype(float)
    x = x / (nx-1) * width / max(width, height)
    y = y / (ny-1) * height / max(width, height)
    xmax, ymax = float(x.max()), float(y.max())
    wx = x + _smooth(rng, x.shape, 5) * rng.uniform(.025, .07)
    wy = y + _smooth(rng, x.shape, 5) * rng.uniform(.025, .07)
    angle = rng.uniform(0, math.tau)
    h = rng.uniform(-.7, .7) * (wx * math.cos(angle) + wy * math.sin(angle))
    ridges = int(rng.integers(2, 7))
    ridge_parameters = []
    for _ in range(ridges):
        cx, cy = rng.uniform(-.1, 1.1) * xmax, rng.uniform(-.1, 1.1) * ymax
        a = angle + rng.normal(0, .65)
        length, breadth = rng.uniform(.15, .65), rng.uniform(.035, .19)
        u = (wx-cx) * math.cos(a) + (wy-cy) * math.sin(a)
        v = -(wx-cx) * math.sin(a) + (wy-cy) * math.cos(a)
        v += .045 * np.sin(u * rng.uniform(5, 15) + rng.uniform(0, math.tau))
        uplift = rng.uniform(.35, 1.1) * (.55 + c["relief"])
        h += uplift * np.exp(-((u/length)**2 + (v/breadth)**2) * .5)
        ridge_parameters.append([float(cx), float(cy), float(a), float(length), float(breadth)])
    h += .12 * _smooth(rng, h.shape, 7) + .027 * _smooth(rng, h.shape, 22)
    h += .008 * _smooth(rng, h.shape, 57)
    # Repeated downhill sediment transfer softens steep talus without erasing ranges.
    for _ in range(7):
        update = np.zeros_like(h)
        for dy, dx in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            difference = h - np.roll(h, (dy, dx), axis=(0, 1))
            move = np.maximum(difference - .018, 0) * .09
            if dy: move[0 if dy == 1 else -1] = 0
            if dx: move[:, 0 if dx == 1 else -1] = 0
            update -= move
            update += np.roll(move, (-dy, -dx), axis=(0, 1))
        h += update
    for _ in range(2):
        dest, flow, filled = _drain(h)
        incision = np.log1p(flow) ** 1.35 * (.0015 + .0065 * c["incision"])
        # A finite channel width prevents the routing raster from becoming a
        # one-cell staircase stamped into every contour and relief shadow.
        h -= gaussian_filter(incision, 1.35)
    dest, flow, filled = _drain(h)
    sea = float(np.quantile(h, rng.uniform(.12, .38)))
    hi = float(np.quantile(h, .995))
    normalized = np.clip((h-sea) / max(hi-sea, .001), 0, 1)
    palettes = [
        ((236, 226, 203), (172, 97, 66), (65, 68, 59), (117, 148, 150)),
        ((231, 226, 207), (178, 152, 82), (60, 94, 103), (169, 185, 177)),
        ((228, 223, 215), (111, 136, 121), (49, 70, 82), (175, 193, 200)),
        ((237, 221, 204), (188, 116, 104), (91, 72, 77), (166, 176, 165)),
    ]
    palette_index = int(rng.integers(len(palettes)))
    paper, mineral, ink, water = [np.array(v, dtype=float) for v in palettes[palette_index]]
    bands = int(9 + c["strata"] * 27)
    q = np.floor(normalized * bands) / bands
    pigment = .15 + .67 * q
    rgb = paper[None, None, :] * (1-pigment[..., None]) + mineral[None, None, :] * pigment[..., None]
    gy, gx = np.gradient(h)
    shade = np.clip((gx * math.cos(angle+.8) + gy * math.sin(angle+.8)) * 650, -20, 16)
    rgb += shade[..., None]
    submerged = h < sea
    depth = np.clip((sea-h) / max(float(np.ptp(h)), 1e-6), 0, .4)
    rgb[submerged] = (water[None, None, :] * (.75+depth[..., None]) + paper[None, None, :] * (.25-depth[..., None]))[submerged]
    image = Image.fromarray(np.uint8(np.clip(rgb, 0, 255))).resize((width, height), Image.Resampling.BICUBIC)
    draw = ImageDraw.Draw(image)
    contour = contourpy.contour_generator(z=h, name="serial")
    sx, sy = (width-1)/(nx-1), (height-1)/(ny-1)
    for i, level in enumerate(np.linspace(sea, hi, bands+1)):
        color = tuple(np.uint8(ink * (.64 if i % 4 == 0 else .28) + paper * (.36 if i % 4 == 0 else .72)))
        for line in contour.lines(float(level)):
            if len(line) > 3:
                draw.line([(float(p[0]*sx), float(p[1]*sy)) for p in line], fill=color, width=max(1, round(width/1400)))
    threshold = 32 + (1-c["incision"]) * 85
    # Flood routing through a filled basin is not an exposed river bed. Omit those
    # segments; otherwise D8 tie-breaking leaves conspicuous parallel grid marks.
    channels = (flow > threshold) & (h > sea) & (filled-h < .008)
    river_count = int(np.count_nonzero(channels))
    visited = np.zeros(h.size, dtype=bool)
    downstream = dest.ravel()
    for first in np.argsort(flow.ravel()):
        if not channels.ravel()[first] or visited[first]: continue
        path = []
        index = int(first)
        while channels.ravel()[index] and not visited[index]:
            iy,ix = divmod(index,nx)
            path.append((float(ix*sx),float(iy*sy)))
            visited[index] = True
            nxt = int(downstream[index])
            if nxt==index: break
            index = nxt
        if len(path)>2:
            iy,ix = divmod(index,nx)
            path.append((float(ix*sx),float(iy*sy)))
            points = np.array(path)
            smoothed = gaussian_filter1d(points, .8, axis=0, mode="nearest")
            smoothed[0],smoothed[-1] = points[0],points[-1]
            weight = max(1, round(math.log1p(float(flow.ravel()[first])/threshold)*width/1000))
            draw.line([tuple(p) for p in smoothed],fill=tuple(np.uint8(ink)),width=min(weight,max(2,round(width/200))))
    # Fine paper variation remains subordinate to relief and channel structure.
    arr = np.asarray(image).astype(np.float32)
    arr += rng.normal(0, 1.25, (height, width, 1))
    image = Image.fromarray(np.uint8(np.clip(arr, 0, 255)))
    return image, {"study": "geology", "seed": int(seed), "controls": c, "ridge_count": ridges, "ridges": ridge_parameters, "palette": palette_index, "land_fraction": float(np.mean(~submerged)), "river_segments": river_count, "strata_count": bands}
