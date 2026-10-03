"""Finishing must preserve empty space, source data and deterministic replay."""
import json
import unittest

import numpy as np

from experiments.studies.perlin_common import density_image
from experiments.studies.perlin_finish import finish_density, material_coordinate


class PerlinFinishTests(unittest.TestCase):
    def setUp(self):
        self.density = np.zeros((96, 112))
        self.density[25:71, 30:82] = np.linspace(.01, 8, 52)
        self.pigment = self.density * np.linspace(0, 1, 112)[None, :]

    def test_disabled_finish_is_exact_legacy_render(self):
        for dtype in (np.float32, np.float64):
            density, pigment = self.density.astype(dtype), self.pigment.astype(dtype)
            for exposure in (None, 1.3):
                image, details = finish_density(density, 7, pigment, exposure=exposure, strength=0)
                self.assertEqual(image.tobytes(), density_image(density, exposure=exposure).tobytes())
                self.assertEqual(details['strength'], 0)

    def test_disabled_float32_exposure_metadata_replays_pixels(self):
        density = np.random.default_rng(712).lognormal(0, 2, (512, 512)).astype(np.float32)
        image, details = finish_density(density, 7, strength=0)
        self.assertEqual(image.tobytes(), density_image(density).tobytes())
        self.assertEqual(image.tobytes(), density_image(density, exposure=details['exposure']).tobytes())

    def test_replay_does_not_mutate_inputs_or_paint_distant_black(self):
        density, pigment = self.density.copy(), self.pigment.copy()
        first, meta = finish_density(density, 11, pigment)
        again, repeated = finish_density(density, 11, pigment)
        np.testing.assert_array_equal(density, self.density)
        np.testing.assert_array_equal(pigment, self.pigment)
        self.assertEqual(first.tobytes(), again.tobytes())
        self.assertEqual(meta, repeated)
        json.dumps(meta, allow_nan=False)
        pixels = np.asarray(first)
        self.assertFalse(pixels[:15].any())
        self.assertFalse(pixels[-15:].any())
        self.assertTrue(np.any(pixels[:, :, 0] != pixels[:, :, 1]))

    def test_material_changes_color_and_not_brightness_support(self):
        first, _ = finish_density(self.density, 3, self.pigment, bloom=0)
        second, _ = finish_density(self.density, 3, self.density - self.pigment, bloom=0)
        self.assertNotEqual(first.tobytes(), second.tobytes())
        self.assertFalse(np.asarray(first)[self.density == 0].any())
        self.assertFalse(np.asarray(second)[self.density == 0].any())

    def test_material_sampling_is_order_independent_and_coherent(self):
        x = np.linspace(-1, 1, 20)
        first = material_coordinate(2, x, x * .7, x * .2)
        np.testing.assert_array_equal(first, material_coordinate(2, x[::-1], x[::-1] * .7, x[::-1] * .2)[::-1])
        self.assertTrue(np.all((first >= 0) & (first <= 1)))
        self.assertLess(float(np.max(np.abs(first - material_coordinate(2, x + 1e-6, x * .7, x * .2)))), 1e-4)

    def test_empty_density_is_black_even_with_full_effects(self):
        image, meta = finish_density(np.zeros((64, 80)), 1)
        self.assertFalse(np.asarray(image).any())
        json.dumps(meta, allow_nan=False)

    def test_invalid_data_fails_before_finishing(self):
        for settings in ({'strength': float('nan')}, {'bloom': -1}, {'exposure': 0}):
            with self.assertRaises(ValueError):
                finish_density(self.density, 1, **settings)
        for pigment in (np.ones((4, 4)), self.density * 2, self.pigment * float('nan')):
            with self.assertRaises(ValueError):
                finish_density(self.density, 1, pigment)


if __name__ == '__main__':
    unittest.main()
