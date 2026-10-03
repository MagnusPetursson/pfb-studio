"""Transport, replay, and projection invariants for the folded-veil audition."""
import json
import unittest
from unittest.mock import patch

import numpy as np

from experiments.studies import folded_veils
from experiments.studies.perlin_common import Perlin, density_image


class FoldedVeilTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls = {"folding": 0.0, "complexity": 0.5}
        original_finish = folded_veils.finish_density

        def capture_deposits(density, seed, **kwargs):
            cls.expected_monochrome = density_image(density)
            cls.deposited_density = density.copy()
            cls.deposited_material = kwargs["color_density"].copy()
            return original_finish(density, seed, **kwargs)

        with patch.object(folded_veils, "finish_density", capture_deposits):
            cls.image, cls.metadata = folded_veils.render(3, 192, 192, cls.controls)
        cls.replay, cls.replay_metadata = folded_veils.render(3, 192, 192, cls.controls)
        cls.portrait, cls.portrait_metadata = folded_veils.render(3, 128, 256, cls.controls)
        cls.monochrome, cls.monochrome_metadata = folded_veils.render(
            3, 192, 192, {**cls.controls, "finish": 0.})

    def test_exact_replay_and_strict_finite_metadata(self):
        np.testing.assert_array_equal(self.image, self.replay)
        self.assertEqual(self.metadata, self.replay_metadata)
        json.dumps(self.metadata, allow_nan=False)
        self.assertTrue(self.metadata["finite_geometry"])
        self.assertEqual(self.metadata["boundary_queries"], 0)
        self.assertEqual(self.metadata["retained_particles"] + self.metadata["escaped_particles"],
                         self.metadata["particles"])
        self.assertEqual(self.image.mode, "RGB")
        self.assertGreater(self.metadata["positive_density_pixels"], 0)
        self.assertGreater(self.metadata["black_pixels"], 192 * 192 // 2)
        self.assertNotEqual(self.metadata["initial_bounds"], self.metadata["world_bounds"])

    def test_finish_keeps_transport_and_zero_restores_legacy_pixels(self):
        np.testing.assert_array_equal(self.monochrome, self.expected_monochrome)
        self.assertFalse(np.array_equal(self.image, self.monochrome))
        for key in self.metadata:
            if key not in ("controls", "black_pixels", "finish"):
                self.assertEqual(self.metadata[key], self.monochrome_metadata[key], key)
        self.assertGreater(float(self.deposited_material.sum()), 0.)
        self.assertTrue((self.deposited_material >= 0).all())
        self.assertTrue((self.deposited_material <= self.deposited_density + 1e-12).all())
        np.testing.assert_array_equal(self.deposited_material[self.deposited_density == 0], 0.)
        low, high = self.metadata["material_coordinate_bounds"]
        self.assertGreater(high - low, .1)
        self.assertGreaterEqual(low, 0.)
        self.assertLessEqual(high, 1.)

    def test_resolution_and_aspect_change_only_projection(self):
        for key in ("sheets", "steps", "noise_seed", "field_frequency", "field_grid",
                    "field_translation", "camera", "initial_bounds", "world_bounds",
                    "projected_bounds", "retained_particles", "boundary_queries"):
            self.assertEqual(self.metadata[key], self.portrait_metadata[key], key)
        self.assertEqual(self.portrait.size, (128, 256))
        # The bbox fit and camera offset must leave real black around the
        # rendered material rather than clip the shape to an image edge.
        for image in (self.image, self.portrait):
            pixels = np.asarray(image)
            self.assertFalse(pixels[0].any())
            self.assertFalse(pixels[-1].any())
            self.assertFalse(pixels[:, 0].any())
            self.assertFalse(pixels[:, -1].any())

    def test_actual_perlin_curl_has_negligible_discrete_divergence(self):
        field, extent, spacing, rms = folded_veils._curl_field(
            Perlin(71), np.array([[.3, 5.4, -7.2], [13.1, -.8, 6.4], [-9.7, 2.3, 1.1]]), .73, 1.)
        divergence = sum(np.gradient(field[axis], spacing, axis=axis) for axis in range(3))
        self.assertLess(float(np.max(np.abs(divergence[2:-2, 2:-2, 2:-2]))), 1e-12)
        self.assertGreater(rms, .1)
        self.assertAlmostEqual(float(np.mean(np.sum(field * field, axis=0))), 1., places=12)
        self.assertEqual(extent, 4.5)

    def test_controls_and_dimensions_reject_invalid_values(self):
        for controls in ({"folding": -1}, {"complexity": 1.01}, {"folding": float("nan")},
                         {"complexity": float("inf")}, {"finish": -0.1},
                         {"finish": float("nan")}, {"invented": .5}):
            with self.subTest(controls=controls), self.assertRaises(ValueError):
                folded_veils.render(1, 32, 32, controls)
        with self.assertRaises(ValueError):
            folded_veils.render(1, 0, 32)


if __name__ == "__main__":
    unittest.main()
