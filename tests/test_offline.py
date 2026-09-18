"""Focused Step 1 mathematics and artifact checks, independent of renderer."""
import hashlib,json,math,re,sys,unittest
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs,pixel_rays
from projection import project,unproject,angle_targets

class Step1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=load_config();cls.cams=camera_specs(cls.c)
        cls.data=json.loads((ROOT/'config/derived_calibration.json').read_text(encoding='utf8'))

    def test_01_baseline_unchanged(self):
        for name,sha in json.loads((ROOT/'reports/baseline_manifest.json').read_text(encoding='utf8')).items():
            with self.subTest(file=name):
                path=ROOT/'assets/baseline'/name
                if not path.exists() and (Path(name).parts[1] in ('sources','drawings') or Path(name).suffix in ('.step','.stl')):
                    self.skipTest('Original source/drawing/CAD omitted from public repository; not hash-verified in this checkout')
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),sha,name)

    def test_02_inheritance_only_authorized_changes(self):
        old=json.loads((ROOT/'assets/baseline/seven_camera_sim_layout_v01/config/layout_parameters.json').read_text(encoding='utf8'))
        for key in ('layout','geometry','nominal_acquisition','frame_convention','customer_source','source_image_observations','assumptions'):
            self.assertEqual(old[key],self.c[key],key)
        self.assertEqual(old['optics']['surround'],self.c['optics']['surround'])
        for key in ('front_main','front_stereo'):
            for attr in old['optics'][key]:
                if attr!='provenance':self.assertEqual(old['optics'][key][attr],self.c['optics'][key][attr])

    def test_03_ids_positions_axes(self):
        expected=[[0,0,0],[0,31.5,0],[0,-31.5,0],[-16,55,20],[-16,55,-20],[-16,-55,20],[-16,-55,-20]]
        self.assertEqual([x['id'] for x in self.cams],[f'C{i}' for i in range(7)])
        for i,cam in enumerate(self.cams):
            np.testing.assert_allclose(cam['position_mm'],expected[i])
            np.testing.assert_allclose(cam['forward_B'],[1,0,0] if i<3 else [0,0,1 if i in (3,5) else -1])
            np.testing.assert_allclose(cam['up_B'],[0,0,1] if i<3 else [-1 if i in (3,5) else 1,0,0])
        self.assertEqual(self.c['layout']['imu_position_mm'],[-18,0,0])
        self.assertEqual(self.data['imu']['id'],'I0')
        self.assertEqual(self.data['imu']['output_hz'],200)

    def test_04_spacing(self):
        pos=np.array([x['position_mm'] for x in self.cams])
        self.assertAlmostEqual(np.linalg.norm(pos[1]-pos[2]),63.)
        np.testing.assert_allclose((pos[1]+pos[2])/2,pos[0])
        self.assertAlmostEqual(np.linalg.norm(pos[3]-pos[5]),110.)
        self.assertAlmostEqual(np.linalg.norm(pos[4]-pos[6]),110.)
        self.assertAlmostEqual(np.linalg.norm(pos[3]-pos[4]),40.)
        self.assertAlmostEqual(np.linalg.norm(pos[5]-pos[6]),40.)

    def test_05_rotations_quaternions_and_units(self):
        for cam,entry in zip(self.cams,self.data['cameras']):
            for key in ('optical','usd'):
                R=np.array(cam['R_B_'+key]);q=np.array(cam['q_B_'+key+'_wxyz'])
                np.testing.assert_allclose(R.T@R,np.eye(3),atol=1e-12)
                self.assertAlmostEqual(np.linalg.det(R),1.)
                np.testing.assert_allclose(Rotation.from_quat(q[[1,2,3,0]]).as_matrix(),R,atol=1e-12)
            np.testing.assert_allclose(np.array(cam['R_B_optical'])@np.diag([1,-1,-1]),cam['R_B_usd'])
            np.testing.assert_allclose(np.array(entry['T_B_cameraOptical_m'])[:3,3],np.array(cam['position_mm'])/1000)

    def test_06_bidirectional_extrinsics(self):
        imu=np.array(self.data['imu']['T_B_IMU_m'])
        np.testing.assert_allclose(imu@self.data['imu']['T_IMU_B_m'],np.eye(4),atol=1e-12)
        for e in self.data['cameras']:
            np.testing.assert_allclose(np.array(e['T_B_cameraOptical_m'])@e['T_cameraOptical_B_m'],np.eye(4),atol=1e-12)
            np.testing.assert_allclose(np.array(e['T_IMU_cameraOptical_m'])@e['T_cameraOptical_IMU_m'],np.eye(4),atol=1e-12)
            np.testing.assert_allclose(imu@e['T_IMU_cameraOptical_m'],e['T_B_cameraOptical_m'],atol=1e-12)

    def test_07_fov_and_principal_points(self):
        for i,cam in enumerate(self.cams):
            o=cam['optics'];w,h=o['resolution']
            self.assertEqual([o['cx_px'],o['cy_px']],[w/2,h/2])
            if i==0:
                self.assertAlmostEqual(math.degrees(2*math.atan(w/2/o['fx_px'])),120)
                self.assertAlmostEqual(math.degrees(2*math.atan(h/2/o['fy_px'])),130)
                self.assertNotEqual(o['fx_px'],o['fy_px'])
            elif i<3:
                self.assertAlmostEqual(math.degrees(w/o['fx_px']),160)
                self.assertAlmostEqual(math.degrees(h/o['fy_px']),130)
                self.assertEqual(o['valid_radius_px'],800)
            else:
                self.assertAlmostEqual(math.degrees(2*480/o['fx_px']),220)
                self.assertEqual(o['valid_radius_px'],480)

    def test_08_roundtrip_and_valid_boundaries(self):
        rng=np.random.default_rng(17)
        for cam in self.cams:
            o=cam['optics'];uv=rng.uniform([0,0],o['resolution'],(300,2))
            pred,valid=project(cam,unproject(cam,uv))
            np.testing.assert_allclose(pred,uv,atol=1e-9)
            rays,mask=pixel_rays(cam,stride=37)
            np.testing.assert_allclose(np.linalg.norm(rays,axis=-1),1.,atol=1e-12)
            if o['model']=='ideal_equidistant':
                _,corner_valid=project(cam,unproject(cam,[[.5,.5]]));self.assertFalse(corner_valid[0])
                r=o['valid_radius_px'];cx=o['cx_px'];cy=o['cy_px']
                for eps,expected in [(-.01,True),(.01,False)]:
                    _,v=project(cam,unproject(cam,[[cx+r+eps,cy]]));self.assertEqual(bool(v[0]),expected)

    def test_09_requested_angles(self):
        for index in (0,1,3):
            for t in angle_targets(self.cams[index]):
                angle=abs(t['angle_deg'])
                expected=angle in ([59,64] if index==0 else [79,64] if index==1 else [0,60,95,105])
                self.assertEqual(t['theoretical_visible'],expected,t['name'])

    def test_10_single_config_artifact_consistency(self):
        sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
        self.assertEqual(self.data['config_sha256'],sha)
        usd=(ROOT/'scenes/rig_v0.2.usda').read_text()
        self.assertEqual(usd.count(sha),8)
        self.assertIn('../assets/baseline/',usd)
        for cam,e in zip(self.cams,self.data['cameras']):self.assertEqual(cam['optics'],e['optics'])
        self.assertIn(str(self.cams[0]['optics']['fy_px']),usd)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Step1Tests))
    (ROOT/'reports/offline_results.json').write_text(json.dumps(dict(scope='OFFLINE_MATH_NOT_RENDERING',tests_run=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),status='PASS' if result.wasSuccessful() else 'FAIL'),indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
