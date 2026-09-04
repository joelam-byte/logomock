import unittest

from app.models import Project
from app.services.geometry import normalize_geometry


class GeometryTests(unittest.TestCase):
    def test_calibration_reprojects_from_millimeters_without_mutating_input(self):
        p = Project.model_validate(dict(
            calibration=dict(product_frame=dict(x=0,y=0,w=400,h=200),width_mm=200),
            frames=[dict(id='f',x=20,y=30,w=300,h=150)],
            schemes=[dict(id='A',frame_id='f',size_mm=dict(w=50,h=20),offset_mm=dict(left=10,bottom=15))]))
        out = normalize_geometry(p)
        self.assertEqual(out.schemes[0].logo_px.model_dump(),dict(x=40,y=110,w=100,h=40))
        self.assertEqual(p.schemes[0].logo_px.w,0)
        p.calibration.width_mm = 400
        out = normalize_geometry(p)
        self.assertEqual(out.schemes[0].logo_px.model_dump(),dict(x=30,y=145,w=50,h=20))

    def test_nonfinite_dimensions_cannot_reach_json(self):
        for value in [float('nan'),float('inf'),-1]:
            with self.assertRaises(ValueError):
                Project.model_validate({'calibration':{'width_mm':value}})

    def test_duplicate_scheme_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            Project.model_validate({'schemes':[{'id':'A'},{'id':'A'}]})


if __name__ == '__main__':
    unittest.main()
