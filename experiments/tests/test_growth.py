"""Inexpensive algorithm-study regression checks; artistic review stays visual."""
import json
import unittest

from experiments.studies import ecologies, membranes


class GrowthStudyTests(unittest.TestCase):
    def test_membrane_replay_and_growth(self):
        controls = {"growth": 0.0}
        first, a = membranes.render(5, 192, 192, controls)
        replay, b = membranes.render(5, 192, 192, controls)
        self.assertEqual(first.mode, "RGB")
        self.assertEqual(first.size, (192, 192))
        self.assertEqual(first.tobytes(), replay.tobytes())
        self.assertEqual(a, b)
        self.assertTrue(a["finite_geometry"])
        self.assertGreater(a["inserted_nodes"], 0)
        self.assertEqual(a["initial_nodes"] + a["inserted_nodes"], a["final_nodes"])
        self.assertLessEqual(a["final_nodes"], a["node_limit"])
        self.assertEqual(a["open_contours"] + a["closed_contours"], a["contours"])
        grown, c = membranes.render(5, 192, 192, {"growth": 0.75})
        self.assertGreater(c["steps"], a["steps"])
        self.assertNotEqual(first.tobytes(), grown.tobytes())
        for metadata in (a, c):
            low, high = metadata["framed_bounds"]
            margin = metadata["frame_margin"]
            self.assertTrue(all(v >= margin - 1e-12 for v in low))
            self.assertTrue(all(v <= 1 - margin + 1e-12 for v in high))
            self.assertGreater(metadata["frame_scale"], 0)
            self.assertLessEqual(metadata["frame_scale"], 1)
            self.assertGreater(metadata["spacing_range"][1], metadata["spacing_range"][0] * 1.25)
        json.dumps(a, allow_nan=False)

    def test_ecology_replay_tree_and_obstacles(self):
        first, a = ecologies.render(3, 192, 192)
        replay, b = ecologies.render(3, 192, 192)
        self.assertEqual(first.mode, "RGB")
        self.assertEqual(first.tobytes(), replay.tobytes())
        self.assertEqual(a, b)
        self.assertTrue(a["finite_geometry"])
        self.assertTrue(a["forest_valid"])
        self.assertEqual(a["edges"], a["nodes"] - a["root_count"])
        self.assertGreater(a["branch_points"], 0)
        self.assertGreater(a["minimum_obstacle_clearance"], 0)
        self.assertEqual(a["initial_sites"], a["consumed_sites"] + a["remaining_sites"])
        self.assertLessEqual(a["nodes"], a["node_limit"])
        different, _ = ecologies.render(4, 192, 192)
        self.assertNotEqual(first.tobytes(), different.tobytes())
        json.dumps(a, allow_nan=False)

    def test_controls_and_portrait(self):
        for module in (membranes, ecologies):
            key = next(iter(module.CONTROLS))
            for invalid in (-0.1, 1.1, float("nan"), float("inf")):
                with self.subTest(study=module.TITLE, invalid=invalid):
                    with self.assertRaises(ValueError):
                        module.render(1, 96, 96, {key: invalid})
            with self.assertRaises(ValueError):
                module.render(1, 0, 96)
            with self.assertRaises(ValueError):
                module.render(1, 96, 96, {"misspelled": 0.5})
            image, metadata = module.render(5, 96, 192, {key: 0.0})
            self.assertEqual(image.size, (96, 192))
            self.assertTrue(metadata["finite_geometry"])

    def test_ecology_density_preserves_selected_composition(self):
        for seed in (1, 3):
            with self.subTest(seed=seed):
                sparse, a = ecologies.render(seed, 128, 128, {"density": 0.0})
                dense, b = ecologies.render(seed, 128, 128, {"density": 1.0})
                # The corner is unpainted; this checks the actual rendered
                # paper as well as all selected layout/appearance metadata.
                self.assertEqual(sparse.getpixel((0, 0)), dense.getpixel((0, 0)))
                self.assertEqual(a["layout"], b["layout"])
                self.assertEqual(a["palette"], b["palette"])
                self.assertEqual(a["root_count"], b["root_count"])
                self.assertLess(a["initial_sites"], b["initial_sites"])
                self.assertGreater(b["nodes"], a["nodes"])
                self.assertNotEqual(sparse.tobytes(), dense.tobytes())
                json.dumps(a, allow_nan=False)
                json.dumps(b, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
