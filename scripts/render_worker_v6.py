"""Capture new native RGB with updated optics and unchanged wearer geometry."""
import sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'outputs/step2_1b_v6/raw';OUT.mkdir(parents=True,exist_ok=True);RPT=ROOT/'reports/step2_1b_v6';RPT.mkdir(parents=True,exist_ok=True)
def write(name,data):(RPT/name).write_text(json.dumps(data,indent=2))
write('render_status.json',{'status':'RUNNING'})
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','anti_aliasing':0,'multi_gpu':False,'sync_loads':False,'disable_viewport_updates':True,'extra_args':['--/app/asyncRendering=false']})
try:
 import numpy as np
 from PIL import Image
 from pxr import Usd,UsdGeom,UsdSkel,UsdLux,UsdShade,Sdf,Gf,Vt,Semantics
 import omni.usd,omni.timeline,omni.replicator.core as rep,carb
 from rig_common import load_config,camera_specs,camera_rotation,quat_wxyz
 from projection import project
 placement=json.loads((ROOT/'config/step2_1b_v6/final_placement.json').read_text());specs=camera_specs(load_config());R=np.array(placement['R_world_B'])
 context=omni.usd.get_context();context.open_stage(str(ROOT/'scenes/step2_1b_v6/indoor_worker.usda'))
 for i in range(150):app.update()
 stage=context.get_stage();stage.SetEditTarget(stage.GetSessionLayer())
 timeline=omni.timeline.get_timeline_interface();timeline.pause();timeline.set_current_time(0)
 for prefix,label in [('/World/Person','step21_wearer'),('/World/Rig','step21_device_final')]:
  api=Semantics.SemanticsAPI.Apply(stage.GetPrimAtPath(prefix),'Step21');api.CreateSemanticTypeAttr().Set('class');api.CreateSemanticDataAttr().Set(label)
 camera_checks=[]
 for c,record in zip(specs,placement['camera_records']):
  prim=stage.GetPrimAtPath(c['prim_path'].replace('/SevenCameraRig','/World/Rig'));m=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0))
  assert np.allclose(m[3,:3],record['world_position_m'],atol=1e-8)
  assert np.allclose(-m[2,:3],record['forward_world'],atol=1e-8)
  assert np.allclose(m[1,:3],record['image_up_world'],atol=1e-8)
  camera_checks.append({'camera_id':c['id'],'world_position_m':m[3,:3].tolist(),'forward_world':(-m[2,:3]).tolist()})
 assert UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/Wearer')).ComputeVisibility()=='invisible'
 sensor_checks=[]
 for c in specs:
  w,h=c['optics']['resolution'];path=c['prim_path'].replace('/SevenCameraRig','/World/Rig');prod=rep.create.render_product(path,(w,h))
  rgb=rep.AnnotatorRegistry.get_annotator('rgb');depth=rep.AnnotatorRegistry.get_annotator('distance_to_camera');rgb.attach([prod]);depth.attach([prod])
  for _ in range(20):app.update()
  rep.orchestrator.step(rt_subframes=24,delta_time=0.,pause_timeline=True);arr=np.asarray(rgb.get_data())[...,:3].copy();d=np.asarray(depth.get_data()).copy().reshape(h,w)
  from projection import unproject
  u,v=np.meshgrid(np.arange(w)+.5,np.arange(h)+.5);uv=np.stack([u,v],axis=-1);rr=unproject(c,uv);_,valid=project(c,rr)
  assert valid.all();Image.fromarray(arr).save(OUT/(c['id']+'.png'));depth_dir=ROOT/'.cache/step2_1b_v6/depth';depth_dir.mkdir(parents=True,exist_ok=True);np.savez_compressed(depth_dir/(c['id']+'_depth.npz'),distance_m=d,valid=valid)
  assert np.isfinite(d[valid]).sum()>1000,(c['id'],'missing depth')
  sensor_checks.append(dict(camera_id=c['id'],resolution=[w,h],center_distance_m=float(d[h//2,w//2]),finite_valid_pixels=int(np.isfinite(d[valid]).sum()),annotation='distance_to_camera',scene_geometry_unchanged=True,position_world_m=(np.array(placement['rig_translation_world_m'])+R@np.array(c['position_mm'])/1000).tolist(),R_world_optical=(R@np.array(c['R_B_optical'])).tolist(),reference_only=c['id'].endswith('_REF'),optics=c['optics']))
  rgb.detach([prod]);depth.detach([prod]);prod.destroy();print('NATIVE_SCENE',c['id'],flush=True)
 write('sensor_view_checks.json',sensor_checks)
 # Cache is generated from evaluated final worker and actual final device meshes.
 meshdata=np.load(ROOT/'.cache/step2_1b_v3/evaluated_meshes.npz');objects=[]
 for name in meshdata.files:
  tri=meshdata[name];objects.append(('/World/Person/'+name if name.startswith('body') else '/World/Rig/'+name,tri[:,0],tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]))
 def first_hit(origin,direction):
  best=float('inf');path=None
  for name,v0,e1,e2 in objects:
   h=np.cross(direction,e2);a=np.einsum('ij,ij->i',e1,h);f=np.divide(1,a,out=np.zeros_like(a),where=np.abs(a)>1e-11);s=origin-v0;u=f*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=f*(q@direction);t=f*np.einsum('ij,ij->i',e2,q);ok=(np.abs(a)>1e-11)&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-5)
   if ok.any() and t[ok].min()<best:best=float(t[ok].min());path=name
  return best,path
 depth_validation=[]
 for record in sensor_checks:
  cid=record['camera_id'];c=next(q for q in specs if q['id']==cid);w,h=record['resolution'];data=np.load(depth_dir/(cid+'_depth.npz'));observed=data['distance_m'];rows=[]
  for y in np.linspace(.06*h,.94*h,13).astype(int):
   for x in np.linspace(.06*w,.94*w,13).astype(int):
    if not data['valid'][y,x]:continue
    ray=unproject(c,[x+.5,y+.5])@np.array(record['R_world_optical']).T;distance,path=first_hit(np.array(record['position_world_m']),ray)
    if path and .001<distance<.7:
     value=float(observed[y,x]);rows.append(dict(pixel=[int(x),int(y)],mesh_distance_m=distance,renderer_distance_m=value,error_m=abs(value-distance),hit=path))
  errors=[a['error_m'] for a in rows];depth_validation.append(dict(camera_id=cid,samples=len(rows),maximum_error_m=max(errors) if errors else None,median_error_m=float(np.median(errors)) if errors else None,errors_over_5mm=sum(e>.005 for e in errors),examples=rows))
 write('depth_validation.json',depth_validation)
 assert sum(r['samples'] for r in depth_validation)>100 and not any(r['errors_over_5mm'] for r in depth_validation),depth_validation
 write('render_status.json',dict(status='PASS',native_RGB_frames=7,camera_checks=camera_checks,config_sha256=placement['config_sha256'],scene='scenes/step2_1b_v6/indoor_worker.usda',source_geometry='v3 unchanged',postprocessing='none',depth_checks='actual final body/device mesh first-hit against native radial depth',loading_status=list(context.get_stage_loading_status())))
except Exception as exc:
 write('render_status.json',{'status':'FAILED','error':str(exc),'traceback':traceback.format_exc()});raise
finally:app.close()
