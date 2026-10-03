"""Focused regression tests for the two equation-based removable studies."""

import json
import unittest

import numpy as np

from experiments.studies import attractors, engravings


class FieldStudiesTests(unittest.TestCase):
    def test_expression_is_independent_of_evaluation_order(self):
        _, metadata = engravings.render(4, 128, 128)
        expression = metadata["expression"]
        x = np.linspace(-1.6, 1.6, 137)
        y = np.sin(x * 1.31)
        expected = engravings.evaluate(expression, x, y)
        # Sampling a final image in another order must not change the function.
        permutation = np.random.default_rng(923).permutation(len(x))
        shuffled = engravings.evaluate(expression, x[permutation], y[permutation])
        np.testing.assert_array_equal(shuffled, expected[permutation])
        self.assertTrue(np.isfinite(expected).all())

    def test_seed_replay_and_json_metadata(self):
        for module in (engravings, attractors):
            with self.subTest(study=module.TITLE):
                first, meta_first = module.render(3, 128, 160)
                second, meta_second = module.render(3, 128, 160)
                self.assertEqual(first.mode, "RGB")
                self.assertEqual(first.size, (128, 160))
                self.assertEqual(first.tobytes(), second.tobytes())
                self.assertEqual(meta_first, meta_second)
                json.dumps(meta_first, allow_nan=False)
                self.assertGreater(np.asarray(first).std(), 1.0)

    def test_structure_is_independent_of_output_resolution(self):
        for module, key in ((engravings, "expression"), (attractors, "program")):
            with self.subTest(study=module.TITLE):
                _, small = module.render(2, 128, 128)
                _, larger = module.render(2, 192, 192)
                self.assertEqual(small[key], larger[key])
                self.assertEqual(small["selected_candidate"], larger["selected_candidate"])

    def test_persistent_state_changes_actual_orbits(self):
        low, low_meta = attractors.render(2, 128, 128, {"persistence": 0.0})
        high, high_meta = attractors.render(2, 128, 128, {"persistence": 1.0})
        self.assertNotEqual(low.tobytes(), high.tobytes())
        self.assertGreater(low_meta["transform_switches"], high_meta["transform_switches"])
        self.assertGreater(low_meta["samples_in_frame"], 0)
        self.assertGreater(high_meta["samples_in_frame"], 0)

    def test_engraving_controls_and_aspect_keep_the_seeded_expression(self):
        _, reference = engravings.render(2, 128, 128)
        for controls, size in (({"fold_scale": 0.0}, (128, 128)),
                               ({"fold_scale": 1.0}, (128, 128)),
                               ({}, (128, 192)), ({}, (192, 128))):
            with self.subTest(controls=controls, size=size):
                _, changed = engravings.render(2, *size, controls)
                self.assertEqual(reference["expression"], changed["expression"])
                self.assertEqual(reference["selected_candidate"], changed["selected_candidate"])
                self.assertEqual(reference["candidate_scores"], changed["candidate_scores"])
                self.assertEqual(reference["palette_index"], changed["palette_index"])

    def test_attractor_controls_keep_candidate_and_material(self):
        _, reference = attractors.render(2, 128, 128)
        for name in ("complexity", "persistence", "spread"):
            for value in (0.0, 1.0):
                with self.subTest(control=name, value=value):
                    image, changed = attractors.render(2, 128, 128, {name: value})
                    self.assertEqual(reference["selected_candidate"], changed["selected_candidate"])
                    self.assertEqual(reference["candidate_scores"], changed["candidate_scores"])
                    a, b = reference["program"], changed["program"]
                    self.assertEqual(a["base_hue"], b["base_hue"])
                    common = min(len(a["colors"]), len(b["colors"]))
                    self.assertEqual(a["colors"][:common], b["colors"][:common])
                    if name == "persistence":
                        self.assertEqual(a, b)
                    elif name == "complexity":
                        self.assertNotEqual(len(a["functions"]), len(b["functions"]))
                        self.assertEqual(a["functions"][:common], b["functions"][:common])
                    self.assertGreater(changed["samples_in_frame"], 0)
                    self.assertGreater(np.asarray(image).std(), 1)

    def test_invalid_control_does_not_enter_numerical_simulation(self):
        for module in (engravings, attractors):
            name = next(iter(module.CONTROLS))
            for value in (-0.1, 1.1, float("nan"), float("inf")):
                with self.subTest(study=module.TITLE, value=value):
                    with self.assertRaises(ValueError):
                        module.render(1, 128, 128, {name: value})


if __name__ == "__main__":
    unittest.main()
