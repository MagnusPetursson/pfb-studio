"""Inertia, resolution independence and rendering-contract checks for the study."""
import json
import unittest

import numpy as np

from experiments.studies import inertial_filaments as study


class InertialFilamentTests(unittest.TestCase):
    def test_constant_flow_relaxation_matches_analytic_solution(self):
        response = np.array((0.025, 0.27, 0.93))
        target = np.tile((1.0, -0.5), (3, 1))
        velocity = np.zeros_like(target)
        for _ in range(20):
            velocity = study._relax_velocity(velocity, target, response, 0.01)
        expected = target * (1 - np.exp(-0.2 / response))[:, None]
        np.testing.assert_allclose(velocity, expected, rtol=1e-12, atol=1e-12)
        self.assertTrue(np.all(np.diff(velocity[:, 0]) < 0))

    def test_response_control_changes_motion_without_rerolling_sources(self):
        normal, normal_weight, baseline = study._simulate(2, study._settings(None))
        slower, slow_weight, changed = study._simulate(2, study._settings({"inertia": 1}))
        count = baseline["particles_per_cohort"]
        self.assertEqual(baseline["program"], changed["program"])
        np.testing.assert_array_equal(normal[0], slower[0])
        np.testing.assert_array_equal(normal[0, :count], normal[0, count:count * 2])
        np.testing.assert_array_equal(normal[0, :count], normal[0, count * 2:])
        # The fast cohort's response does not depend on the control. Its exact
        # trajectories must therefore survive a change to the other cohorts.
        np.testing.assert_array_equal(normal[:, :count], slower[:, :count])
        self.assertFalse(np.array_equal(normal[:, count:], slower[:, count:]))
        self.assertTrue(np.all(np.diff(baseline["mean_velocity_lag_by_cohort"]) > 0))
        self.assertGreater(baseline["endpoint_separation_from_fast"][2], 0.1)
        for history, weights, metadata in ((normal, normal_weight, baseline),
                                           (slower, slow_weight, changed)):
            self.assertTrue(np.isfinite(history).all())
            self.assertTrue(np.isfinite(weights).all())
            self.assertTrue((weights >= 0).all())
            self.assertEqual(metadata["escaped_particle_count"], 0)
            json.dumps(metadata, allow_nan=False)

    def test_exact_replay_and_resolution_independent_world(self):
        small, first = study.render(1, 96, 128)
        larger, second = study.render(1, 192, 128)
        replay, third = study.render(1, 192, 128)
        self.assertEqual(small.size, (96, 128))
        self.assertEqual(larger.mode, "RGB")
        self.assertEqual(larger.tobytes(), replay.tobytes())
        self.assertEqual(second, third)
        self.assertEqual(first["program"], second["program"])
        self.assertEqual(first["trajectory_sha256"], second["trajectory_sha256"])
        pixels = np.asarray(larger)
        self.assertTrue((pixels == 0).all(axis=2).any())
        self.assertGreater(int(pixels.max()), 100)
        self.assertTrue((pixels[:, :, 0] <= pixels[:, :, 1]).all())
        self.assertTrue((pixels[:, :, 1] <= pixels[:, :, 2]).all())
        json.dumps(second, allow_nan=False)

    def test_seeds_change_field_and_emitter_configuration(self):
        a, b = study._program(1), study._program(2)
        self.assertNotEqual(a["emitters"], b["emitters"])
        self.assertNotEqual(a["large_scale"], b["large_scale"])
        self.assertNotEqual(a["anisotropy"], b["anisotropy"])

    def test_domain_exit_stops_without_wrapping_or_clamping(self):
        position = np.array(((study._DOMAIN - 0.01, 0.0), (0.0, 0.0)))
        velocity = np.array(((2.0, 0.0), (0.0, 0.1)))
        active = np.array((True, True))
        moved, escaped = study._advance_particles(position, velocity, active, 0.1)
        np.testing.assert_array_equal(escaped, (True, False))
        np.testing.assert_array_equal(moved[0], position[0])
        np.testing.assert_allclose(moved[1], (0.0, 0.01))
        still, _ = study._advance_particles(moved, -velocity, ~escaped, 0.1)
        np.testing.assert_array_equal(still[0], position[0])

    def test_invalid_controls_and_dimensions_fail(self):
        for name in study.CONTROLS:
            for value in (float("nan"), float("inf"), -0.1, 1.1):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        study.render(1, 128, 128, {name: value})
        with self.assertRaises(ValueError):
            study.render(1, 128, 128, {"unknown": 0.5})
        for width, height in ((32, 128), (128, 32), (128.5, 128), (True, 128)):
            with self.assertRaises(ValueError):
                study.render(1, width, height)


if __name__ == "__main__":
    unittest.main()
