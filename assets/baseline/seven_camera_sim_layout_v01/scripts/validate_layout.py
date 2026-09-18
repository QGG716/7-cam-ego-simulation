#!/usr/bin/env python3
"""Offline validation; does not claim that Isaac or SLAM has been executed."""
from __future__ import annotations
import json, math, re, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import cadquery as cq
import ezdxf
import yaml
from rig_common import ROOT,load_config,camera_specs,geometry_specs,pixel_rays,nearest_hit
from build_models import shape_for

def main():
    cfg=load_config(); cams=camera_specs(cfg);geo=geometry_specs(cfg);checks=[]
    def check(name,ok,detail=''):
        checks.append({'name':name,'status':'PASS' if bool(ok) else 'FAIL','detail':detail})
    check('seven_camera_count',len(cams)==7)
    poses={c['id']:np.array(c['position_mm']) for c in cams}
    check('front_baseline_exact_63_mm',np.isclose(np.linalg.norm(poses['C1']-poses['C2']),63,atol=1e-12))
    check('main_camera_is_midpoint',np.allclose(poses['C0'],(poses['C1']+poses['C2'])/2))
    for a,b in [('C3','C4'),('C5','C6')]:check(f'{a}_{b}_same_xy',np.allclose(poses[a][:2],poses[b][:2]))
    nominal=json.loads((ROOT/'config/nominal_extrinsics.json').read_text())
    yml=yaml.safe_load((ROOT/'config/nominal_extrinsics.yaml').read_text())
    check('yaml_json_equivalent',nominal==yml)
    shapes=[(g,shape_for(g)) for g in geo]
    for g,s in shapes:check('geometry_valid_'+g['name'],s.isValid())
    for c,e in zip(cams,nominal['cameras']):
        R=np.array(c['R_B_optical']);U=np.array(c['R_B_usd']);q=np.array(c['q_B_usd_wxyz'])
        check(c['id']+'_rotation_orthonormal',np.allclose(R.T@R,np.eye(3),atol=1e-12) and np.isclose(np.linalg.det(R),1))
        check(c['id']+'_usd_optical_forward_mapping',np.allclose(U@[0,0,-1],c['forward_B']))
        check(c['id']+'_usd_optical_up_mapping',np.allclose(U@[0,1,0],c['up_B']))
        check(c['id']+'_quaternion_to_matrix',np.allclose(Rotation.from_quat(q[[1,2,3,0]]).as_matrix(),U))
        T=np.array(e['T_B_cameraOptical_m']);Ti=np.array(e['T_cameraOptical_B_m'])
        check(c['id']+'_extrinsic_inverse',np.allclose(T@Ti,np.eye(4)))
        check(c['id']+'_imu_chain',np.allclose(T@e['T_cameraOptical_IMU_m'],nominal['imu']['T_B_IMU_m']))
        inside=[g['name'] for g,s in shapes if s.isInside(cq.Vector(*c['position_mm']),1e-7)]
        check(c['id']+'_optical_origin_outside_opaque_solids',not inside,','.join(inside))
        rays,valid=pixel_rays(c,stride=16)
        check(c['id']+'_nominal_unit_rays',np.allclose(np.linalg.norm(rays[valid],axis=-1),1,atol=1e-12))
    for f in (ROOT/'models').glob('*.step'):
        solids=cq.importers.importStep(str(f)).solids().vals();check('step_roundtrip_'+f.name,bool(solids) and all(s.isValid() for s in solids),f'{len(solids)} valid solids')
    d=ezdxf.readfile(ROOT/'drawings/seven_camera_layout_mm.dxf');audit=d.audit()
    check('dxf_audit',not audit.has_errors,f'{len(audit.errors)} errors');check('dxf_units_mm',d.units==4)
    urdf=ET.parse(ROOT/'models/seven_camera_frames.urdf').getroot()
    check('urdf_fixed_tf_tree',len(urdf.findall('joint'))==8 and all(j.get('type')=='fixed' for j in urdf.findall('joint')))
    # This checks the explicit text payload only, not the USD grammar or renderer behavior.
    usd=(ROOT/'models/seven_camera_rig.usda').read_text()
    check('usda_text_has_seven_camera_definitions',len(re.findall(r'def Camera\s+"',usd))==7)
    check('usda_text_units_one_meter','metersPerUnit = 1' in usd)
    check('usda_text_z_up','upAxis = "Z"' in usd)
    check('no_lut_schema_authored','OmniLensDistortionLutAPI' not in usd)
    report={'scope':'OFFLINE_CAD_AND_NUMERICAL_LAYOUT_ONLY','configuration':cfg['design_revision'],
            'checks':checks,'passed':sum(x['status']=='PASS' for x in checks),'failed':sum(x['status']=='FAIL' for x in checks),
            'not_executed':['USD runtime/pxr parser (not installed in build environment)','NVIDIA Isaac RTX rendering','Camera / IMU motion-time acquisition','SLAM or VIO estimation','real hardware optical or structural validation']}
    (ROOT/'validation/offline_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(f'{report["passed"]} passed, {report["failed"]} failed. Isaac/SLAM NOT executed.')
    for e in checks:
        if e['status']=='FAIL':print(e)
    if report['failed']:raise SystemExit(1)

if __name__=='__main__':main()
