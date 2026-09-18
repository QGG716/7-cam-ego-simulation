"""Derive calibration and a relative USD overlay; never rebuild baseline CAD."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs,transform


def build():
    c=load_config(); cams=camera_specs(c)
    sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
    imu=transform(np.eye(3),np.array(c['layout']['imu_position_mm'])*.001)
    for cam in cams:
        T=transform(np.array(cam['R_B_optical']),np.array(cam['position_mm'])*.001)
        cam.update(T_B_cameraOptical_m=T.tolist(),T_cameraOptical_B_m=np.linalg.inv(T).tolist(),
                   T_IMU_cameraOptical_m=(np.linalg.inv(imu)@T).tolist(),T_cameraOptical_IMU_m=(np.linalg.inv(T)@imu).tolist())
    data=dict(design_revision=c['design_revision'],config_sha256=sha,conventions=c['frame_convention'],
              cameras=cams,imu=dict(id='I0',T_B_IMU_m=imu.tolist(),T_IMU_B_m=np.linalg.inv(imu).tolist(),
              output_hz=c['nominal_acquisition']['imu_output_hz'],sampling_status='NOT_IMPLEMENTED'))
    (ROOT/'config/derived_calibration.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    # Keep the original device as a reference and author only stronger camera opinions.
    lines=['#usda 1.0','(defaultPrim = "World"\n metersPerUnit = 1\n upAxis = "Z")',
           'def Xform "World" {','def Xform "Rig" (prepend references = @../assets/baseline/seven_camera_sim_layout_v01/models/seven_camera_rig.usda@</SevenCameraRig>) {',
           'double3 xformOp:translate = ('+', '.join(map(str,c['simulation']['rig_world_translation_m']))+')',
           'uniform token[] xformOpOrder = ["xformOp:translate"]',
           f'custom string sim:version = "{c["design_revision"]}"',f'custom string sim:configSha256 = "{sha}"',
           'over "Sensors" {']
    for cam in cams:
        o=cam['optics'];w,h=o['resolution']
        lines += [f'over "{cam["id"]}_{cam["name"]}" {{',
                  f'custom double sim:fx = {o["fx_px"]}',f'custom double sim:fy = {o["fy_px"]}',
                  f'custom double sim:vfov = {o["derived_vfov_deg"]}',
                  f'custom string sim:configSha256 = "{sha}"',
                  f'float2 clippingRange = ({c["simulation"]["near_clip_m"]}, {c["simulation"]["far_clip_m"]})']
        if cam['id']=='C0':
            # Schema application requires prim metadata, emitted below by replacement.
            lines += ['uniform token omni:lensdistortion:model = "opencvPinhole"',
                      f'float omni:lensdistortion:opencvPinhole:fx = {o["fx_px"]}',
                      f'float omni:lensdistortion:opencvPinhole:fy = {o["fy_px"]}',
                      f'float omni:lensdistortion:opencvPinhole:cx = {o["cx_px"]}',
                      f'float omni:lensdistortion:opencvPinhole:cy = {o["cy_px"]}',
                      f'int2 omni:lensdistortion:opencvPinhole:imageSize = ({w}, {h})']
            for k in ('k1','k2','p1','p2','k3','k4','k5','k6','s1','s2','s3','s4'):
                lines.append(f'float omni:lensdistortion:opencvPinhole:{k} = 0')
        else:
            lines.append('custom token cameraProjectionType = "fisheyePolynomial"')
            attrs=dict(fthetaWidth=w,fthetaHeight=h,fthetaCx=o['cx_px'],fthetaCy=o['cy_px'],
                       fthetaMaxFov=o['radial_full_fov_deg'],fthetaPolyA=0,fthetaPolyB=1/o['fx_px'],
                       fthetaPolyC=0,fthetaPolyD=0,fthetaPolyE=0)
            for k,v in attrs.items():lines.append(f'custom float {k} = {v}')
        lines.append('}')
    lines += ['}','}','}']
    text='\n'.join(lines).replace('over "C0_front_main" {','over "C0_front_main" (prepend apiSchemas = ["OmniLensDistortionOpenCvPinholeAPI"]) {')
    (ROOT/'scenes/rig_v0.2.usda').write_text(text+'\n',encoding='utf8')
    print(json.dumps({'version':c['design_revision'],'config_sha256':sha,'cameras':len(cams)}))

if __name__=='__main__': build()
