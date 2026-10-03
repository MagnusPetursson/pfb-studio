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
            self.assertLessEqual(float(np.abs(history).max()), study._DOMAIN)
            self.assertGreaterEqual(metadata["escaped_particle_count"], 0)
            self.assertLessEqual(metadata["escaped_particle_count"], history.shape[1])
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
        monochrome, unstyled = study.render(1, 192, 128, {"finish": 0})
        self.assertEqual(second["trajectory_sha256"], unstyled["trajectory_sha256"])
        self.assertEqual(second["density_sha256"], unstyled["density_sha256"])
        self.assertEqual(second["material_sha256"], unstyled["material_sha256"])
        self.assertNotEqual(larger.tobytes(), monochrome.tobytes())
        pixels = np.asarray(monochrome)
        self.assertTrue((pixels[:, :, 0] <= pixels[:, :, 1]).all())
        self.assertTrue((pixels[:, :, 1] <= pixels[:, :, 2]).all())
        json.dumps(second, allow_nan=False)

    def test_single_curtain_is_an_area_with_continuous_response_times(self):
        program = study._program(1)
        program["emitters"] = program["emitters"][:1]
        origin, _, strength, response, _, count, _ = study._launch(1, program, study._settings(None))
        covariance = np.cov(origin[:count].T)
        self.assertGreater(float(np.linalg.eigvalsh(covariance).min()), 0.002)
        self.assertGreater(float(strength[:count].std()), 0.05)
        # Distinct response times cover a continuum inside each cohort.
        for cohort in response.reshape(3, count):
            self.assertGreater(len(np.unique(cohort)), count * 0.95)
            self.assertGreater(float(cohort.max() / cohort.min()), 1.8)

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
        fade = study._boundary_weight(np.array(((0, 0), (study._DOMAIN - 0.4, 0),
                                                (study._DOMAIN, 0))))
        np.testing.assert_allclose(fade, (1, 0.5, 0), atol=1e-12)

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
