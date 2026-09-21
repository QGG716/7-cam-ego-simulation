"""Build the new calibration and camera-only USD layer; prior stages remain read-only."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs,transform

def main():
 c=load_config();cams=camera_specs(c);sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest();out=ROOT/'config/step2_1b_v6';scene=ROOT/'scenes/step2_1b_v6';out.mkdir(parents=True,exist_ok=True);scene.mkdir(parents=True,exist_ok=True)
 imu=transform(np.eye(3),np.array(c['layout']['imu_position_mm'])/1000)
 for cam in cams:
  T=transform(np.array(cam['R_B_optical']),np.array(cam['position_mm'])/1000);cam.update(T_B_cameraOptical_m=T.tolist(),T_cameraOptical_B_m=np.linalg.inv(T).tolist(),T_IMU_cameraOptical_m=(np.linalg.inv(imu)@T).tolist(),T_cameraOptical_IMU_m=(np.linalg.inv(T)@imu).tolist())
 data=dict(design_revision=c['design_revision'],config_sha256=sha,cameras=cams,imu=dict(id='I0',T_B_IMU_m=imu.tolist(),T_IMU_B_m=np.linalg.inv(imu).tolist()))
 (out/'derived_calibration.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 p=json.loads((ROOT/'config/step2_1b_v3/final_placement.json').read_text());oldhash=p['config_sha256'];p['config_sha256']=sha;p['geometry_source']='config/step2_1b_v3/final_placement.json';p['fit_status_provenance']='Prior v3 static fit, unchanged geometry; not a new fit experiment';p['previous_config_sha256']=oldhash
 for cam,row in zip(cams,p['camera_records']):row['projection']=cam['optics']
 (out/'final_placement.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 lines=['#usda 1.0','(defaultPrim="World"\n metersPerUnit=1\n upAxis="Z"\n subLayers=[@../step2_1b_v3/indoor_worker.usda@])','over "World" {\nover "Rig" {\nover "Sensors" {']
 for cam in cams:
  o=cam['optics'];w,h=o['resolution'];backend='OpenCvPinhole' if cam['id']=='C0' else 'Lut';lines.append(f'over "{cam["id"]}_{cam["name"]}" (prepend apiSchemas=["OmniLensDistortion{backend}API"]) {{');lines.extend([f'custom double sim:fx = {o["fx_px"]}',f'custom double sim:fy = {o["fy_px"]}',f'custom double sim:hfov = {o["hfov_deg"]}',f'custom double sim:vfov = {o["derived_vfov_deg"]}',f'custom string sim:configSha256 = "{sha}"'])
  if cam['id']=='C0':
   lines.append('uniform token omni:lensdistortion:model = "opencvPinhole"')
   for name,value in dict(fx=o['fx_px'],fy=o['fy_px'],cx=w/2,cy=h/2).items():lines.append(f'float omni:lensdistortion:opencvPinhole:{name} = {value}')
   lines.append(f'int2 omni:lensdistortion:opencvPinhole:imageSize = ({w},{h})')
  else:
   profile='front' if cam['id'] in ['C1','C2'] else 'surround';lines.extend(['uniform token omni:lensdistortion:model = "lut"',f'float omni:lensdistortion:lut:nominalWidth = {w}',f'float omni:lensdistortion:lut:nominalHeight = {h}',f'float2 omni:lensdistortion:lut:opticalCenter = ({w/2},{h/2})',f'asset omni:lensdistortion:lut:rayEnterDirectionTexture = @../../config/step2_1b_v6/lut/{profile}_enter.exr@',f'asset omni:lensdistortion:lut:rayExitPositionTexture = @../../config/step2_1b_v6/lut/{profile}_exit.exr@',f'custom float fthetaMaxFov = {o["radial_full_fov_deg"]}'])
  lines.append('}')
 lines.extend(['}','}','}']);(scene/'indoor_worker.usda').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('Calibration and camera-only layer generated')
if __name__=='__main__':main()
