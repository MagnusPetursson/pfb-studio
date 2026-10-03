"""Small shared primitives for the black-background Perlin auditions.

Seeded lattice gradients and quintic interpolation implement coherent Perlin
noise. The renderer only accumulates particle deposits; it adds no background
texture, bloom, blur, or synthetic edges.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


class Perlin:
    """Vectorized, signed gradient noise with a seeded 256-cell permutation."""

    _grad2 = np.array([[1, 0], [-1, 0], [0, 1], [0, -1],
                       [1, 1], [-1, 1], [1, -1], [-1, -1]], dtype=float)
    _grad2[4:] /= np.sqrt(2)
    _grad3 = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0],
                       [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                       [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1]], dtype=float) / np.sqrt(2)

    def __init__(self, seed: int):
        permutation = np.random.default_rng(seed).permutation(256)
        self._p = np.concatenate((permutation, permutation))

    @staticmethod
    def _fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def noise2(self, x, y):
        x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        fx, fy = x - ix, y - iy
        u, v = self._fade(fx), self._fade(fy)
        ix, iy = ix & 255, iy & 255
        result = np.zeros_like(fx)
        for dx in (0, 1):
            for dy in (0, 1):
                g = self._grad2[self._p[self._p[ix + dx] + iy + dy] & 7]
                dot = g[..., 0] * (fx - dx) + g[..., 1] * (fy - dy)
                result += dot * (u if dx else 1 - u) * (v if dy else 1 - v)
        return result

    def noise3(self, x, y, z):
        x, y, z = np.broadcast_arrays(np.asarray(x, dtype=float),
                                      np.asarray(y, dtype=float), np.asarray(z, dtype=float))
        ix, iy, iz = [np.floor(a).astype(np.int64) for a in (x, y, z)]
        fx, fy, fz = x - ix, y - iy, z - iz
        u, v, w = self._fade(fx), self._fade(fy), self._fade(fz)
        ix, iy, iz = ix & 255, iy & 255, iz & 255
        result = np.zeros_like(fx)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    hashed = self._p[self._p[self._p[ix + dx] + iy + dy] + iz + dz]
                    g = self._grad3[hashed % 12]
                    dot = g[..., 0] * (fx - dx) + g[..., 1] * (fy - dy) + g[..., 2] * (fz - dz)
                    result += dot * (u if dx else 1 - u) * (v if dy else 1 - v) * (w if dz else 1 - w)
        return result


def splat(density: np.ndarray, x, y, weight=1.0) -> None:
    """Accumulate bilinear point deposits in pixel coordinates, clipping at edges."""
    x, y, weight = [a.ravel() for a in np.broadcast_arrays(
        np.asarray(x, dtype=float), np.asarray(y, dtype=float), np.asarray(weight, dtype=float))]
    if not (np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(weight).all()):
        raise ValueError("Particle deposits must be finite")
    if np.any(weight < 0):
        raise ValueError("Particle deposits cannot subtract light")
    height, width = density.shape
    visible = (x > -1) & (x < width) & (y > -1) & (y < height) & (weight > 0)
    x, y, weight = x[visible], y[visible], weight[visible]
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    flat = density.ravel()
    for dx in (0, 1):
        for dy in (0, 1):
            px, py = ix + dx, iy + dy
            valid = (px >= 0) & (px < width) & (py >= 0) & (py < height)
            amount = weight * (fx if dx else 1 - fx) * (fy if dy else 1 - fy)
            flat += np.bincount(py[valid] * width + px[valid], weights=amount[valid],
                                minlength=width * height).astype(density.dtype, copy=False)


def density_image(density: np.ndarray, exposure: float | None = None,
                  tint=(205, 225, 255)) -> Image.Image:
    """Compress highlights in one pale hue, retaining exact black at zero density."""
    if not np.isfinite(density).all() or np.any(density < 0):
        raise ValueError("Density must be finite and nonnegative")
    positive = density[density > 0]
    if not len(positive):
        return Image.new("RGB", (density.shape[1], density.shape[0]), (0, 0, 0))
    if exposure is None:
        exposure = max(float(np.quantile(positive, 0.995)) * 0.44, 1e-12)
    if not np.isfinite(exposure) or exposure <= 0:
        raise ValueError("Exposure must be positive and finite")
    light = np.power(-np.expm1(-density.astype(float) / exposure), 0.92)
    pixels = np.rint(light[..., None] * np.asarray(tint)).clip(0, 255).astype(np.uint8)
    return Image.fromarray(pixels)
