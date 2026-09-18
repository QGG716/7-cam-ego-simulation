"""Minimal independent Step 2 regression checks; no Step 1 artifact writes."""
import unittest,sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rig_common import nearest_hit,pixel_rays,camera_specs,load_config
from analyze_step2 import trace,inside,components
class Step2(unittest.TestCase):
 def test_known_intersections(self):
  objects=[dict(kind='box',center_mm=[0,0,0],size_mm=[2,2,2]),dict(kind='ellipsoid',center_mm=[0,0,0],radii_mm=[1,2,3]),dict(kind='cylinder',a_mm=[0,0,-2],b_mm=[0,0,2],radius_mm=1)]
  for obj in objects:
   with self.subTest(kind=obj['kind']):
    self.assertAlmostEqual(float(nearest_hit([-3,0,0],np.array([[1.,0,0]]),obj)[0]),2.)
    self.assertTrue(np.isinf(nearest_hit([-3,4,0],np.array([[1.,0,0]]),obj)[0]));self.assertTrue(inside([0,0,0],obj))
  with np.errstate(invalid='ignore'):self.assertAlmostEqual(float(nearest_hit([0,0,4],np.array([[0.,0,-1]]),objects[2])[0]),2.)
 def test_unique_nearest_and_units(self):
  objs=[dict(id=1,kind='box',center_mm=[3,0,0],size_mm=[2,2,2]),dict(id=2,kind='box',center_mm=[6,0,0],size_mm=[2,2,2])]
  ids,dist=trace([0,0,0],np.array([[[1.,0,0],[1.,0,0]]]),np.array([[True,False]]),objs)
  self.assertEqual(ids.tolist(),[[1,0]]);self.assertAlmostEqual(float(dist[0,0]),.002);self.assertTrue(np.isnan(dist[0,1]))
 def test_axes_and_back_hemisphere(self):
  cams=camera_specs(load_config())
  for cam in cams:
   rays,valid=pixel_rays(cam,stride=20);self.assertTrue(np.allclose(np.linalg.norm(rays,axis=-1),1))
   if cam['id'] in ['C3','C4','C5','C6']:self.assertTrue(((rays@np.array(cam['forward_B'])<0)&valid).any());self.assertFalse(valid[0,0])
   o=cam['optics'];from projection import unproject
   self.assertTrue(np.allclose(np.array(cam['R_B_optical'])@unproject(cam,[o['cx_px'],o['cy_px']]),cam['forward_B']))
 def test_frozen(self):
  before=json.loads((ROOT/'reports/step2/frozen_before.json').read_text())
  for name,sha in before.items():
   p=ROOT/name
   if not p.exists() and (name=='reports/local_preflight.log' or p.suffix.lower() in ['.pdf','.step','.stl','.dxf','.zip'] or '/sources/' in name or '/drawings/' in name or '/source_review/' in name):continue
   self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),sha,name)
 def test_artifact_invariants(self):
  report=json.loads((ROOT/'outputs/step2/camera_occlusion_summary.json').read_text())
  self.assertEqual(report['optical_centers_inside_opaque_geometry'],[])
  for cam in camera_specs(load_config()):
   arrays={m:np.load(ROOT/f'outputs/step2/{m}/{cam["id"]}_analytic.npz') for m in ['ideal','body','worn']}
   self.assertFalse(arrays['ideal']['blocked'].any());self.assertFalse((arrays['body']['blocked']&~arrays['worn']['blocked']).any())
   self.assertTrue(np.array_equal(arrays['worn']['added_blocked'],arrays['worn']['blocked']&~arrays['body']['blocked']))
   for mode,data in arrays.items():
    self.assertFalse((data['blocked']&~data['valid']).any());self.assertTrue(np.array_equal(data['first_hit_id']>0,data['blocked']))
    row=next(r for r in report['rows'] if r['camera_id']==cam['id'] and r['mode']==mode)
    self.assertEqual(row['N_valid'],int(data['valid'].sum()));self.assertEqual(row['N_blocked'],sum(x['N_blocked'] for x in row['components']))
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(unittest.defaultTestLoader.loadTestsFromTestCase(Step2))
 (ROOT/'reports/step2/test_results.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),status='PASS' if result.wasSuccessful() else 'FAIL'),indent=2));sys.exit(not result.wasSuccessful())
