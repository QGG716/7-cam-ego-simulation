"""Step 2.1b-v3: external renders of the final worker and adapted mounting layer."""
import sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'outputs/step2_1b_v3/debug';OUT.mkdir(parents=True,exist_ok=True)
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2))
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
 placement=json.loads((ROOT/'config/step2_1b_v3/final_placement.json').read_text());specs=camera_specs(load_config());R=np.array(placement['R_world_B'])
 context=omni.usd.get_context();context.open_stage(str(ROOT/'scenes/step2_1b_v3/indoor_worker.usda'))
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
 # Native sensor-view RGB and radial depth, before presentation-only lighting/materials.
 assert not any(q.IsA(UsdGeom.Mesh) and 'hardhat' in q.GetName().lower() for q in Usd.PrimRange(stage.GetPrimAtPath('/World/Person')))
 for removed_path in placement['worker']['removed_prims']:assert not stage.GetPrimAtPath(removed_path).IsActive()
 sensor_checks=[];capture_specs=list(specs)
 for cid,sourceid,z in [('UP_REF','C3',.020),('DOWN_REF','C4',-.020)]:
  source=next(c for c in specs if c['id']==sourceid);c=dict(source);c['id']=cid;c['position_mm']=[-16,0,z*1000];path='/World/FigureReference/'+cid
  prim=UsdGeom.Camera.Define(stage,path).GetPrim();prim.GetReferences().AddInternalReference(source['prim_path'].replace('/SevenCameraRig','/World/Rig'))
  rotation=R@np.array(source['R_B_usd']);position=np.array(placement['rig_translation_world_m'])+R@np.array(c['position_mm'])/1000;m=np.eye(4);m[:3,:3]=rotation.T;m[3,:3]=position;xf=UsdGeom.Xformable(prim);xf.ClearXformOpOrder();xf.AddTransformOp(opSuffix='referenceWorld').Set(Gf.Matrix4d(m.tolist()));c['prim_path']=path;capture_specs.append(c)
 for c in capture_specs:
  w,h=c['optics']['resolution'];path=c['prim_path'].replace('/SevenCameraRig','/World/Rig');prod=rep.create.render_product(path,(w,h))
  rgb=rep.AnnotatorRegistry.get_annotator('rgb');depth=rep.AnnotatorRegistry.get_annotator('distance_to_camera');rgb.attach([prod]);depth.attach([prod])
  for _ in range(20):app.update()
  rep.orchestrator.step(rt_subframes=24,delta_time=0.,pause_timeline=True);arr=np.asarray(rgb.get_data())[...,:3].copy();d=np.asarray(depth.get_data()).copy().reshape(h,w)
  from projection import unproject
  u,v=np.meshgrid(np.arange(w)+.5,np.arange(h)+.5);uv=np.stack([u,v],axis=-1);rr=unproject(c,uv);_,valid=project(c,rr)
  masked=arr.copy();masked[~valid]=0;Image.fromarray(masked).save(OUT/(c['id']+'_scene.png'));np.savez_compressed(OUT/(c['id']+'_depth.npz'),distance_m=d,valid=valid)
  assert np.isfinite(d[valid]).sum()>1000,(c['id'],'missing depth')
  sensor_checks.append(dict(camera_id=c['id'],resolution=[w,h],center_distance_m=float(d[h//2,w//2]),finite_valid_pixels=int(np.isfinite(d[valid]).sum()),annotation='distance_to_camera',scene_geometry_unchanged=True,position_world_m=(np.array(placement['rig_translation_world_m'])+R@np.array(c['position_mm'])/1000).tolist(),R_world_optical=(R@np.array(c['R_B_optical'])).tolist(),reference_only=c['id'].endswith('_REF'),optics=c['optics']))
  rgb.detach([prod]);depth.detach([prod]);prod.destroy();print('NATIVE_SCENE',c['id'],flush=True)
 write('sensor_view_checks.json',sensor_checks)
 # Only presentation background and light change. No source layer is saved.
 UsdGeom.Imageable(stage.GetPrimAtPath('/World/Room')).GetVisibilityAttr().Set('invisible')
 dome=UsdLux.DomeLight.Define(stage,'/World/FigureOnly/Dome');dome.CreateIntensityAttr(650.);dome.CreateColorAttr(Gf.Vec3f(1,1,1))
 key=UsdLux.DistantLight.Define(stage,'/World/FigureOnly/Key');key.CreateIntensityAttr(1400.);key.CreateAngleAttr(20.)
 key.AddRotateXYZOp().Set(Gf.Vec3f(25,30,25))
 carb.settings.get_settings().set('/rtx/post/histogram/enabled',False)
 # Dark neutral presentation material: session-only, geometry and sensor assets untouched.
 ink=UsdShade.Material.Define(stage,'/World/FigureOnly/DeviceInk');shader=UsdShade.Shader.Define(stage,'/World/FigureOnly/DeviceInk/Surface');shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.025,.035,.05));shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.65);ink.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
 for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/Rig')):
  if prim.IsA(UsdGeom.Mesh):UsdShade.MaterialBindingAPI.Apply(prim).Bind(ink)
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
  cid=record['camera_id'];c=next(q for q in capture_specs if q['id']==cid);w,h=record['resolution'];data=np.load(OUT/(cid+'_depth.npz'));observed=data['distance_m'];rows=[]
  for y in np.linspace(.06*h,.94*h,13).astype(int):
   for x in np.linspace(.06*w,.94*w,13).astype(int):
    if not data['valid'][y,x]:continue
    ray=unproject(c,[x+.5,y+.5])@np.array(record['R_world_optical']).T;distance,path=first_hit(np.array(record['position_world_m']),ray)
    if path and .001<distance<.7:
     value=float(observed[y,x]);rows.append(dict(pixel=[int(x),int(y)],mesh_distance_m=distance,renderer_distance_m=value,error_m=abs(value-distance),hit=path))
  errors=[a['error_m'] for a in rows];depth_validation.append(dict(camera_id=cid,samples=len(rows),maximum_error_m=max(errors) if errors else None,median_error_m=float(np.median(errors)) if errors else None,errors_over_5mm=sum(e>.005 for e in errors),examples=rows))
 write('depth_validation.json',depth_validation)
 samples=[]
 for c,record in zip(specs,placement['camera_records']):
  origin=np.array(record['world_position_m']);rotation=R@np.array(c['R_B_optical'])
  for theta in [0,30,60,80,95,105,110]:
   for phi in range(0,360,30):
    t,p=np.deg2rad([theta,phi]);optical=np.array([np.sin(t)*np.cos(p),np.sin(t)*np.sin(p),np.cos(t)])
    if not project(c,optical)[1]:continue
    direction=rotation@optical;distance,path=first_hit(origin,direction)
    if path and distance<.65:samples.append(dict(camera_id=c['id'],theta_deg=theta,phi_deg=phi,origin=origin.tolist(),direction=direction.tolist(),distance_m=distance,hit_path=path,hit_world=(origin+distance*direction).tolist()))
 write('intersection_examples.json',samples)
 z=placement['rig_translation_world_m'][2];y=placement['rig_translation_world_m'][1]
 views={
 'body':dict(target=[0,0,.94],direction=[.6,-2,.10],width_m=1.02,resolution=[850,1750]),
 'head':dict(target=[0,y+.045,z-.025],direction=[.9,-1.8,.65],width_m=.46,resolution=[1500,1150]),
 'front':dict(target=[0,y-.07,z-.04],direction=[1,-1.8,.60],width_m=1.20,resolution=[1400,1250]),
 'up':dict(target=[0,y+.01,z+.10],direction=[1,-1.8,.65],width_m=1.10,resolution=[1400,1250]),
 'down':dict(target=[0,y+.01,z-.17],direction=[1,-1.8,.65],width_m=1.10,resolution=[1400,1250]),
 'fit_front':dict(target=[0,y+.07,z],direction=[0,-1,.04],width_m=.43,resolution=[1500,1200]),
 'fit_left':dict(target=[0,y+.10,z],direction=[1,0,.10],width_m=.46,resolution=[1500,1200]),
 'fit_right':dict(target=[0,y+.10,z],direction=[-1,0,.10],width_m=.46,resolution=[1500,1200]),
 'fit_toprear':dict(target=[0,y+.10,z],direction=[.4,1,1.4],width_m=.46,resolution=[1500,1200])}
 for name,v in views.items():
  target=np.array(v['target']);d=np.array(v['direction']);d/=np.linalg.norm(d);pos=target+d*5.;rot=camera_rotation(target-pos,[0,0,1]);q=quat_wxyz(rot@np.diag([1.,-1.,-1.]));w,h=v['resolution'];focal=36*5/v['width_m']
  cam=UsdGeom.Camera.Define(stage,'/World/FigureOnly/'+name);cam.AddTranslateOp().Set(Gf.Vec3d(*pos));cam.AddOrientOp().Set(Gf.Quatf(q[0],Gf.Vec3f(*q[1:])));cam.CreateHorizontalApertureAttr(36.);cam.CreateVerticalApertureAttr(36*h/w);cam.CreateFocalLengthAttr(focal);cam.CreateClippingRangeAttr(Gf.Vec2f(.0001,100));cam.CreateFStopAttr(0.)
  prod=rep.create.render_product(str(cam.GetPath()),(w,h));rgb=rep.AnnotatorRegistry.get_annotator('rgb');seg=rep.AnnotatorRegistry.get_annotator('instance_segmentation',init_params={'colorize':False});rgb.attach([prod]);seg.attach([prod])
  for _ in range(30):app.update()
  rep.orchestrator.step(rt_subframes=32,delta_time=0.,pause_timeline=True);arr=np.array(rgb.get_data())[...,:3];data=seg.get_data();labels=np.array(data['data']);mask=np.zeros((h,w),bool)
  for k,path in data['info']['idToLabels'].items():
   semantics=str(data['info'].get('idToSemantics',{}).get(str(k),{}));path=str(path)
   if path.startswith(('/World/Person','/World/Rig')) or 'step21_wearer' in semantics or 'step21_device_' in semantics or 'step21_mount_' in semantics:mask|=labels==int(k)
  assert mask.sum()>1000,(name,data['info']);rgba=np.dstack((arr,mask.astype(np.uint8)*255));Image.fromarray(rgba).save(OUT/(name+'_rgba.png'))
  v.update(position_world_m=pos.tolist(),R_world_optical=rot.tolist(),fx_px=w*focal/36,fy_px=w*focal/36)
  rgb.detach([prod]);seg.detach([prod]);prod.destroy();print('EXTERNAL_CAPTURE',name,flush=True)
 write('external_views.json',views);write('render_status.json',dict(status='PASS',baseline_commit='956d479333a543b43dd546b4744983685f2e4a87',scene='scenes/step2_1b_v3/indoor_worker.usda',person_height_m=placement['worker']['final_height_m'],camera_checks=camera_checks,external_frames=len(views),formal_dataset_frames=0,technical_sensor_view_frames=7,reference_view_frames=2,source_layers_saved=False,background='Office hidden in anonymous session layer; 650 dome + 1400 distant key; neutral dark material on device meshes for figure only',loading_status=list(context.get_stage_loading_status())))
except Exception as exc:
 write('render_status.json',{'status':'FAILED','error':str(exc),'traceback':traceback.format_exc()});raise
finally:app.close()
