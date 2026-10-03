"""Seeded material color and restrained finishing for deposited Perlin light.

The originals motivate related/complementary palettes, motion-linked color,
highlight bloom and fine noise. Here color travels with the simulated material;
finishing never paints a background. Geometry and its random streams stay separate.
"""
from __future__ import annotations

import colorsys
import math

import numpy as np
from scipy.ndimage import gaussian_filter

from .perlin_common import Perlin, density_image


def material_coordinate(seed, x, y, z=None):
    """Coherent source pigment, sampled before transport and carried by particles."""
    noise = Perlin(int(np.random.default_rng(np.random.SeedSequence([int(seed), 62119])).integers(2**31)))
    if z is None:
        broad = noise.noise2(np.asarray(x) * .83 + 17.1, np.asarray(y) * .83 - 8.6)
        fine = noise.noise2(np.asarray(x) * 2.3 - 21.8, np.asarray(y) * 2.3 + 4.9)
    else:
        broad = noise.noise3(np.asarray(x) * .83 + 17.1, np.asarray(y) * .83 - 8.6, np.asarray(z) * .83 + 3.7)
        fine = noise.noise3(np.asarray(x) * 2.3 - 21.8, np.asarray(y) * 2.3 + 4.9, np.asarray(z) * 2.3 - 11.2)
    return np.clip(.5 + .95 * broad + .22 * fine, 0, 1)


def _palette(seed):
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 73051]))
    hue = float(rng.uniform(0, 1))
    offsets = [0, float(rng.uniform(.07, .15)), float(rng.uniform(.40, .56))]
    saturation = [float(rng.uniform(.55, .78)), .48, float(rng.uniform(.5, .72))]
    return np.asarray([colorsys.hsv_to_rgb((hue + offset) % 1, sat, 1.)
                       for offset, sat in zip(offsets, saturation)])


def finish_density(density, seed, color_density=None, exposure=None, strength=1.0,
                   grain=.06, bloom=.10, detail=.20):
    """Finish a scalar light deposit and its optional density-weighted pigment.

    strength=0 exactly reproduces the unmodified monochrome density renderer.
    Fine Perlin modulation is multiplicative within occupied pixels. Bloom is
    finite-radius highlight light, not a background lift. Inputs are not mutated.
    """
    original_density = np.asarray(density)
    density = np.asarray(density, dtype=float)
    if density.ndim != 2 or not density.size or not np.isfinite(density).all() or np.any(density < 0):
        raise ValueError("Density must be a nonempty, finite, nonnegative 2D array")
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (strength, grain, bloom, detail)):
        raise ValueError("Finishing controls must be finite and in [0, 1]")
    if color_density is not None:
        color_density = np.asarray(color_density, dtype=float)
        if (color_density.shape != density.shape or not np.isfinite(color_density).all()
                or np.any(color_density < 0) or np.any(color_density > density + np.maximum(density, 1) * 1e-5)):
            raise ValueError("Pigment deposits must match density and lie between zero and density")
    occupied = density > 0
    positive = density[occupied]
    if exposure is None:
        exposure_samples = original_density[occupied] if strength == 0 else positive
        exposure = max(float(np.quantile(exposure_samples, .995)) * .44, 1e-12) if len(positive) else 1.
    if not math.isfinite(exposure) or exposure <= 0:
        raise ValueError("Exposure must be positive and finite")
    palette = _palette(seed)
    metadata = {
        "version": 1, "strength": float(strength), "exposure": float(exposure),
        "palette_rgb": np.rint(palette * 255).astype(int).tolist(),
        "grain": float(grain * strength), "bloom": float(bloom * strength),
        "local_contrast": float(detail * strength), "background": [0, 0, 0],
        "color_source": "advected material" if color_density is not None else "density",
    }
    if strength == 0 or not len(positive):
        return density_image(original_density, exposure=exposure), metadata

    height, width = density.shape
    pixel_scale = max(min(width, height) / 768., .125)
    log_density = np.log1p(density / exposure)
    local = gaussian_filter(log_density, max(.6, 1.8 * pixel_scale), mode="constant")
    # Bound the gain: detail should reveal striations without outlining surfaces.
    gain = np.exp(np.clip(log_density - local, -.6, .6) * detail * strength)
    yy, xx = np.mgrid[:height, :width]
    noise = Perlin(int(np.random.default_rng(np.random.SeedSequence([int(seed), 98173])).integers(2**31)))
    micro = noise.noise2(xx * .63 + .317, yy * .63 + .713)
    textured = density * gain * (1 + grain * strength * micro * 2)
    light = np.power(-np.expm1(-textured / exposure), .92)

    if color_density is None:
        coordinate = light
    else:
        coordinate = np.divide(color_density, density, out=np.zeros_like(density), where=occupied)
    # Stretch only the deposited material's range; empty pixels cannot affect it.
    low, high = np.quantile(coordinate[occupied], [.04, .96])
    span = max(float(high - low), .12)
    coordinate = np.clip((coordinate - (low + high) / 2) / span + .5, 0, 1)
    metadata["material_coordinate_range"] = [float(low), float(high)]
    index = np.minimum((coordinate * 2).astype(int), 1)
    fraction = (coordinate * 2 - index)[..., None]
    pigment = palette[index] * (1 - fraction) + palette[index + 1] * fraction
    # Dense seams tend toward pale light while translucent bodies retain color.
    white = (.23 * light ** 3)[..., None]
    pigment = pigment * (1 - white) + white
    rgb = light[..., None] * pigment
    if bloom:
        highlight = np.maximum(light - .58, 0)[..., None] * pigment
        halo = gaussian_filter(highlight, (max(.5, 1.15 * pixel_scale), max(.5, 1.15 * pixel_scale), 0),
                               mode="constant", truncate=3)
        rgb += bloom * halo
    if strength < 1:
        mono = np.asarray(density_image(density, exposure=exposure), dtype=float) / 255
        rgb = mono * (1 - strength) + rgb * strength
    from PIL import Image
    return Image.fromarray(np.rint(rgb * 255).clip(0, 255).astype(np.uint8)), metadata
