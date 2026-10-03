"""Mechanism and reproducibility checks for the branched-light audition."""
import json
import unittest

import numpy as np

from experiments.studies import branched_light


class BranchedLightTests(unittest.TestCase):
    def test_perlin_force_changes_momentum_from_ballistic_control(self):
        straight, zero = branched_light.render(2, 96, 96, {"refraction": 0.0})
        bent, active = branched_light.render(2, 96, 96)
        self.assertEqual(zero["scene"], active["scene"])
        self.assertLess(zero["maximum_displacement_from_ballistic"], 1e-10)
        self.assertEqual(zero["mean_momentum_change"], 0.0)
        self.assertGreater(active["mean_momentum_change"], .05)
        self.assertGreater(active["mean_displacement_from_ballistic"], .05)
        self.assertGreater(active["potential_standard_deviation"], .01)
        self.assertNotEqual(straight.tobytes(), bent.tobytes())
        self.assertEqual(active["scene"]["tint"], [205, 225, 255])
        self.assertTrue(np.any(np.all(np.asarray(bent) == 0, axis=2)))
        json.dumps(active, allow_nan=False)

    def test_replay_and_resolution_leave_world_transport_unchanged(self):
        first, first_meta = branched_light.render(3, 96, 96)
        second, second_meta = branched_light.render(3, 96, 96)
        _, larger_meta = branched_light.render(3, 128, 128)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(first_meta, second_meta)
        for key in ("scene", "potential_grid", "integration_steps", "ray_count",
                    "mean_displacement_from_ballistic", "mean_momentum_change"):
            self.assertEqual(first_meta[key], larger_meta[key], key)

    def test_extreme_aspects_keep_potential_allocation_bounded(self):
        for aspect in (.125, 8):
            potential, gradient, bounds = branched_light._potential(branched_light._scene(2), aspect)
            self.assertLessEqual(max(potential.shape), 1024)
            self.assertTrue(np.isfinite(potential).all())
            self.assertTrue(np.isfinite(gradient).all())
            self.assertEqual(bounds, [-1.35 * aspect, 1.35 * aspect, -1.35, 1.35])

    def test_invalid_controls_fail_before_simulation(self):
        for values in ({"refraction": float("nan")}, {"distance": 1.1}, {"unknown": .5}):
            with self.assertRaises(ValueError):
                branched_light.render(1, 64, 64, values)


if __name__ == "__main__":
    unittest.main()
