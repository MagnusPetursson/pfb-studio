"""Algorithm invariants for the isolated regional studies; not aesthetic scores."""
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np


def load(name):
    path = Path(__file__).parents[1] / "studies" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


geology, cells, cities = (load(name) for name in ("geology", "cells", "cities"))


class RegionInvariants(unittest.TestCase):
    def test_drainage_has_outlets_and_conserves_rainfall(self):
        terrain = np.full((13, 17), 2.0)
        terrain[3:10, 4:13] = -1.0
        terrain[0, 8] = 0.0
        dest, flow, filled = geology._drain(terrain)
        np.testing.assert_array_less(terrain-1e-12, filled)
        outlets = dest.ravel() == np.arange(terrain.size)
        self.assertAlmostEqual(float(flow.ravel()[outlets].sum()), terrain.size)
        for start in range(terrain.size):
            visited = set()
            index = start
            while int(dest.ravel()[index]) != index:
                self.assertNotIn(index, visited)
                visited.add(index)
                nxt = int(dest.ravel()[index])
                self.assertLess(filled.ravel()[nxt], filled.ravel()[index])
                y,x = divmod(index,terrain.shape[1]); yy,xx = divmod(nxt,terrain.shape[1])
                self.assertLessEqual(max(abs(y-yy),abs(x-xx)),1)
                index = nxt

    def test_unequal_division_preserves_region_area(self):
        polygon = [(0.,0.), (2.,0.), (1.8,1.4), (.2,1.)]
        normal = np.array((.7,.3))
        a = cells._clip(polygon,normal,.43)
        b = cells._clip(polygon,-normal,-.43)
        self.assertGreater(cells._area(a),0)
        self.assertGreater(cells._area(b),0)
        self.assertNotAlmostEqual(cells._area(a),cells._area(b))
        self.assertAlmostEqual(cells._area(a)+cells._area(b),cells._area(polygon))

    def test_inset_respects_winding_and_collapse(self):
        square=[(0.,0.),(1.,0.),(1.,1.),(0.,1.)]
        for polygon in (square,list(reversed(square))):
            self.assertAlmostEqual(cells._area(cells._inset(polygon,.1)),.64)
            self.assertEqual(cells._inset(polygon,.6),[])

    def test_road_crossings_and_parallel_segments(self):
        result=cities._intersection((0.,0.),(2.,0.),(1.,-1.),(1.,1.))
        self.assertEqual(result,(.5,(1.,0.)))
        self.assertIsNone(cities._intersection((0.,0.),(2.,0.),(0.,1.),(2.,1.)))
        self.assertIsNone(cities._intersection((0.,0.),(2.,0.),(0.,0.),(0.,1.)))

    def test_render_contract_and_repeatability(self):
        for module in (geology,cells,cities):
            with self.subTest(study=module.TITLE):
                a,meta=module.render(3,192,128)
                b,again=module.render(3,192,128)
                self.assertEqual(a.size,(192,128))
                self.assertEqual(a.mode,"RGB")
                self.assertEqual(a.tobytes(),b.tobytes())
                self.assertEqual(meta,again)
                json.dumps(meta,allow_nan=False)

    def test_invalid_controls_fail_before_drawing(self):
        for module in (geology,cells,cities):
            key=next(iter(module.CONTROLS))
            for value in (float("nan"),float("inf"),-.1,1.1):
                with self.subTest(study=module.TITLE,value=value):
                    with self.assertRaises(ValueError): module.render(1,128,128,{key:value})
            with self.assertRaises(ValueError): module.render(1,128,128,{"unknown":.5})
            with self.assertRaises(ValueError): module.render(1,32,128)

    def test_cutouts_preserve_region_materials(self):
        for seed in (1,5):
            with self.subTest(seed=seed):
                closed,low=cells.render(seed,256,256,{"cutouts":0})
                opened,high=cells.render(seed,256,256,{"cutouts":1})
                self.assertEqual(low["palette"],high["palette"])
                self.assertEqual(low["region_materials"],high["region_materials"])
                self.assertEqual(low["open_region_ids"],[])
                self.assertGreater(len(high["open_region_ids"]),0)
                self.assertNotEqual(closed.tobytes(),opened.tobytes())

    def test_city_growth_controls_preserve_water_palette(self):
        for control in ("density","order"):
            with self.subTest(control=control):
                a,low=cities.render(3,192,128,{control:0})
                b,high=cities.render(3,192,128,{control:1})
                self.assertEqual(low["water_palette_index"],high["water_palette_index"])
                self.assertEqual(low["water_color"],high["water_color"])
                self.assertNotEqual(a.tobytes(),b.tobytes())


if __name__=="__main__":
    unittest.main()
