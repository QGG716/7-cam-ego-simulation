"""New H/V calibration checks, including backward compatibility with the prior optics."""
import unittest,sys,json,math,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs,pixel_rays,geometry_specs
from projection import project,unproject
class OpticsHV(unittest.TestCase):
 def test_requested_centerline_fov(self):
  for cam in camera_specs(load_config()):
   h,v=(120,87) if cam['id']=='C0' else (160,120) if cam['id'] in ['C1','C2'] else (188,133)
   o=cam['optics'];w,hh=o['resolution']
   for theta,axis,pixel in [(h/2,0,[w,hh/2]),(-h/2,0,[0,hh/2]),(v/2,1,[w/2,hh]),(-v/2,1,[w/2,0])]:
    a=math.radians(theta);ray=np.array([0.,0.,math.cos(a)]);ray[axis]=math.sin(a);uv,valid=project(cam,ray);np.testing.assert_allclose(uv,pixel,atol=1e-10)
    np.testing.assert_allclose(unproject(cam,pixel),ray,atol=1e-12)
    outside=math.radians(theta+math.copysign(.1,theta));ray[axis]=math.sin(outside);ray[2]=math.cos(outside);self.assertFalse(bool(project(cam,ray)[1]))
 def test_roundtrip_sampling_and_full_domain(self):
  rng=np.random.default_rng(39)
  for cam in camera_specs(load_config()):
   o=cam['optics'];w,h=o['resolution'];uv=rng.uniform([.1,.1],[w-.1,h-.1],(500,2));r=unproject(cam,uv);back,valid=project(cam,r);np.testing.assert_allclose(back,uv,atol=1e-9);self.assertTrue(valid.all())
   rb,mask=pixel_rays(cam,37);u,v=np.meshgrid(np.arange(0,w,37)+.5,np.arange(0,h,37)+.5);np.testing.assert_allclose(rb,unproject(cam,np.stack([u,v],axis=-1))@np.array(cam['R_B_optical']).T,atol=1e-12);self.assertTrue(mask.all())
 def test_geometry_unchanged(self):
  old=load_config(ROOT/'config/step2_1b_v6/previous_rig_sim.json');new=load_config();self.assertEqual(geometry_specs(old),geometry_specs(new));self.assertEqual(old['layout'],new['layout'])
  for a,b in zip(camera_specs(old),camera_specs(new)):
   for key in ['position_mm','forward_B','up_B','R_B_optical','R_B_usd']:self.assertEqual(a[key],b[key])
   self.assertEqual(a['optics']['resolution'],b['optics']['resolution'])
 def test_active_calibration_and_render_provenance(self):
  cfg=load_config();sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
  data=json.loads((ROOT/cfg['active_calibration']).read_text(encoding='utf8'))
  self.assertEqual(data['config_sha256'],sha)
  stage=(ROOT/cfg['active_scene']).read_text(encoding='utf8');self.assertEqual(stage.count(sha),7)
  for cam,entry in zip(camera_specs(cfg),data['cameras']):self.assertEqual(cam['optics'],entry['optics'])
  status=json.loads((ROOT/'reports/step2_1b_v6/render_status.json').read_text());self.assertEqual(status['status'],'PASS');self.assertEqual(status['config_sha256'],sha);self.assertEqual(status['native_RGB_frames'],7)
  for entry in json.loads((ROOT/'config/step2_1b_v6/lut/manifest.json').read_text())['records']:
   self.assertEqual(hashlib.sha256((ROOT/entry['file']).read_bytes()).hexdigest(),entry['sha256'])
 def test_legacy_projection_unchanged(self):
  old=load_config(ROOT/'config/step2_1b_v6/previous_rig_sim.json')
  for c in camera_specs(old)[1:]:
   o=c['optics'];uv=np.array([[o['cx_px'],o['cy_px']],[100,200],[500,900]],float);xy=uv-[o['cx_px'],o['cy_px']];radius=np.linalg.norm(xy,axis=-1);theta=radius/o['fx_px'];k=np.divide(np.sin(theta),radius,out=np.full_like(radius,1/o['fx_px']),where=radius>0);expected=np.c_[xy*k[:,None],np.cos(theta)];np.testing.assert_allclose(unproject(c,uv),expected,atol=1e-14)
   _,valid=project(c,expected);self.assertEqual(valid.tolist(),(radius<=o['valid_radius_px']+1e-10).tolist())
if __name__=='__main__':unittest.main(verbosity=2)
