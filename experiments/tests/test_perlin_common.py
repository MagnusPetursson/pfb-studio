"""Numerical invariants for actual gradient noise and light deposition."""
import unittest

import numpy as np

from experiments.studies.perlin_common import Perlin, density_image, splat


class PerlinPrimitiveTests(unittest.TestCase):
    def test_seed_and_sample_order_do_not_depend_on_call_history(self):
        noise = Perlin(1234)
        x = np.linspace(-3.17, 5.42, 59)
        expected = noise.noise3(x, x * .31, x * -.72)
        noise.noise2(x, x)
        np.testing.assert_array_equal(expected, noise.noise3(x[::-1], x[::-1] * .31, x[::-1] * -.72)[::-1])
        np.testing.assert_array_equal(expected, Perlin(1234).noise3(x, x * .31, x * -.72))
        self.assertGreater(float(np.max(np.abs(expected - Perlin(1235).noise3(x, x * .31, x * -.72)))), .05)

    def test_gradient_noise_is_zero_at_lattice_points_and_continuous_across_them(self):
        noise = Perlin(83)
        integers = np.arange(-4, 6)
        np.testing.assert_array_equal(noise.noise2(integers, integers), np.zeros(10))
        np.testing.assert_array_equal(noise.noise3(integers, integers, integers), np.zeros(10))
        for sample in (lambda x: noise.noise2(x, .371), lambda x: noise.noise3(x, .371, -.52)):
            h = 1e-5
            center, left, right = sample(integers), sample(integers - h), sample(integers + h)
            np.testing.assert_allclose((center - left) / h, (right - center) / h, atol=1e-6)

    def test_interior_splat_conserves_light_with_overlapping_particles(self):
        density = np.zeros((16, 16), dtype=np.float64)
        splat(density, [4.3, 4.3, 6.7], [7.8, 7.8, 5.2], [1., 3., 2.])
        self.assertAlmostEqual(float(density.sum()), 6.)
        self.assertGreater(density[8, 4], density[5, 7])
        self.assertEqual(float(density[0, 0]), 0.)

    def test_tone_mapping_preserves_empty_black_and_intensity_order(self):
        density = np.array([[0., .1, 1., 10., 100.]])
        pixels = np.asarray(density_image(density))
        np.testing.assert_array_equal(pixels[0, 0], [0, 0, 0])
        self.assertTrue((np.diff(pixels[0, :, 2].astype(int)) >= 0).all())
        self.assertGreater(int(pixels[0, -1, 2]), 200)


if __name__ == "__main__":
    unittest.main()
