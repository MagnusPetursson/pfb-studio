"""Mechanism and reproducibility checks for the branched-light audition."""
import json
import unittest
from unittest.mock import patch

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
        self.assertGreater(active["launch_material"]["radiance_maximum"], active["launch_material"]["radiance_minimum"])
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
            potential = branched_light._Potential(branched_light._scene(2))
            forces = potential.force(np.array([[-.66 * aspect, .5], [.66 * aspect, -.5]]), .5)
            self.assertTrue(np.isfinite(forces).all())
            self.assertLessEqual(len(potential.tiles), 2)
            self.assertLessEqual(max(potential.metadata()["potential_grid"]), 515)
            self.assertEqual(potential.exterior_samples, 0)

    def test_tiles_share_gradients_and_evaluate_beyond_old_field_bounds(self):
        potential = branched_light._Potential(branched_light._scene(2))
        left = potential._tile(0, 0)
        right = potential._tile(1, 0)
        np.testing.assert_array_equal(left[:, :, -1], right[:, :, 0])
        seam = potential.cells * potential.spacing
        points = np.array([[seam - 1e-8, 1], [seam + 1e-8, 1], [-8, 0], [12, 4]])
        forces = potential.force(points, .5)
        np.testing.assert_allclose(forces[0], forces[1], atol=1e-5, rtol=0)
        np.testing.assert_array_equal(forces, potential.force(points, .5))
        self.assertTrue(np.isfinite(forces).all())
        self.assertEqual(potential.exterior_samples, 0)
        # A genuine finite difference of the scalar field checks a remote tile.
        point = np.array([1800, -900]) * potential.spacing
        offsets = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]]) * potential.spacing
        values = branched_light._potential_value(potential.scene, potential.noise,
                                                 point[0] + offsets[:, 0], point[1] + offsets[:, 1])
        expected = -.5 * np.array([values[0] - values[1], values[2] - values[3]]) / (2 * potential.spacing)
        np.testing.assert_allclose(potential.force(point[None, :], .5)[0], expected, atol=1e-11, rtol=1e-11)

    def test_finish_changes_material_without_changing_transport(self):
        plain, plain_meta = branched_light.render(11, 96, 96, {"finish": 0})
        finished, finished_meta = branched_light.render(11, 96, 96, {"finish": 1})
        self.assertNotEqual(plain.tobytes(), finished.tobytes())
        for key in ("scene", "potential_grid", "integration_steps", "ray_count",
                    "mean_displacement_from_ballistic", "mean_momentum_change", "camera_bounds",
                    "density_exposure", "density_maximum", "ray_samples_in_frame"):
            self.assertEqual(plain_meta[key], finished_meta[key], key)
        self.assertEqual(finished_meta["potential_exterior_samples"], 0)
        low, high = np.asarray(finished_meta["camera_bounds"])
        actual_low, actual_high = np.asarray(finished_meta["deposited_world_bounds"])
        self.assertTrue(np.all(actual_low > low))
        self.assertTrue(np.all(actual_high < high))

    def test_maximum_controls_keep_paths_finite_and_inside_fitted_camera(self):
        _, metadata = branched_light.render(20, 64, 64, {"distance": 1, "refraction": 1})
        self.assertEqual(metadata["potential_exterior_samples"], 0)
        self.assertLessEqual(metadata["trajectory_capacity_bytes"], 1355 * 18432 * 2 * 4)
        low, high = np.asarray(metadata["camera_bounds"])
        actual_low, actual_high = np.asarray(metadata["deposited_world_bounds"])
        self.assertTrue(np.all(actual_low > low))
        self.assertTrue(np.all(actual_high < high))
        json.dumps(metadata, allow_nan=False)

    def test_packet_texture_changes_deposits_but_preserves_transport_and_palette(self):
        deposits = []
        finish = branched_light.finish_density

        def capture(density, *args, **kwargs):
            deposits.append(density.copy())
            return finish(density, *args, **kwargs)

        with patch.object(branched_light, "finish_density", side_effect=capture):
            _, smooth = branched_light.render(2, 96, 96, {"texture": 0})
            _, textured = branched_light.render(2, 96, 96, {"texture": 1})
        self.assertFalse(np.array_equal(deposits[0], deposits[1]))
        for key in ("scene", "camera_bounds", "deposited_world_bounds", "integration_steps",
                    "mean_displacement_from_ballistic", "maximum_displacement_from_ballistic",
                    "mean_momentum_change", "potential_bounds", "potential_tile_count", "ray_samples_in_frame"):
            self.assertEqual(smooth[key], textured[key], key)
        self.assertEqual(smooth["finish"]["palette_rgb"], textured["finish"]["palette_rgb"])
        self.assertEqual(smooth["deposition"]["packet_count"], smooth["ray_samples_in_frame"])
        self.assertEqual(smooth["deposition"]["retention_probability"], 1)
        self.assertGreater(textured["deposition"]["packet_count"], 85000)
        self.assertLess(textured["deposition"]["packet_count"], 95000)
        self.assertEqual(smooth["finish"]["bloom"], .10)
        self.assertLess(textured["finish"]["bloom"], smooth["finish"]["bloom"])

    def test_invalid_controls_fail_before_simulation(self):
        for values in ({"refraction": float("nan")}, {"distance": 1.1}, {"texture": -.1}, {"unknown": .5}):
            with self.assertRaises(ValueError):
                branched_light.render(1, 64, 64, values)


if __name__ == "__main__":
    unittest.main()
