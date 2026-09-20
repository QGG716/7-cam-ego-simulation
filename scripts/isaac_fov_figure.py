"""Step 2.1b: external-only render of the frozen Step 2.1 composed scene."""
import sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'outputs/step2_1b/debug';OUT.mkdir(parents=True,exist_ok=True)
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2))
manifest=json.loads((ROOT/'reports/step2_1b/input_manifest.json').read_text())
for name,expected in manifest.items():
 actual=hashlib.sha256((ROOT/name).read_text(encoding='utf-8-sig').replace('\r\n','\n').rstrip().encode()).hexdigest()
 assert actual==expected,('Baseline differs',name)
write('render_status.json',{'status':'RUNNING'})
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','anti_aliasing':0,'multi_gpu':False,'sync_loads':False,'disable_viewport_updates':True,'extra_args':['--/app/asyncRendering=false']})
try:
 import numpy as np
 from PIL import Image
 from pxr import Usd,UsdGeom,UsdSkel,UsdLux,UsdShade,Sdf,Gf,Vt
 import omni.usd,omni.timeline,omni.replicator.core as rep,carb
 from rig_common import load_config,camera_specs,camera_rotation,quat_wxyz
 from projection import project
 placement=json.loads((ROOT/'outputs/step2_1/placement.json').read_text());specs=camera_specs(load_config());R=np.array(placement['R_world_B'])
 context=omni.usd.get_context();context.open_stage(str(ROOT/'scenes/step2_1/indoor_wearer.usda'))
 for i in range(150):app.update()
 stage=context.get_stage();stage.SetEditTarget(stage.GetSessionLayer())
 timeline=omni.timeline.get_timeline_interface();timeline.pause();timeline.set_current_time(0)
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
 camera_checks=[]
 for c,record in zip(specs,placement['camera_records']):
  prim=stage.GetPrimAtPath(c['prim_path'].replace('/SevenCameraRig','/World/Rig'));m=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0))
  assert np.allclose(m[3,:3],record['world_position_m'],atol=1e-8)
  assert np.allclose(-m[2,:3],record['forward_world'],atol=1e-8)
  assert np.allclose(m[1,:3],record['image_up_world'],atol=1e-8)
  camera_checks.append({'camera_id':c['id'],'world_position_m':m[3,:3].tolist(),'forward_world':(-m[2,:3]).tolist()})
 assert UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/Wearer')).ComputeVisibility()=='invisible'
 # Actual evaluated person and actual device mesh triangles, used for a few example rays only.
 cache=UsdSkel.Cache();person=stage.GetPrimAtPath('/World/Person')
 skroot=next(UsdSkel.Root(p) for p in Usd.PrimRange(person) if p.IsA(UsdSkel.Root));skeleton=next(UsdSkel.Skeleton(p) for p in Usd.PrimRange(person) if p.IsA(UsdSkel.Skeleton))
 cache.Populate(skroot,Usd.PrimDefaultPredicate);xforms=cache.GetSkelQuery(skeleton).ComputeSkinningTransforms(0);sm=np.array(UsdGeom.Xformable(skeleton).ComputeLocalToWorldTransform(0));objects=[];person_points=[]
 for rootpath in ['/World/Person','/World/Rig']:
  for prim in Usd.PrimRange(stage.GetPrimAtPath(rootpath)):
   if not prim.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(prim).ComputeVisibility()=='invisible':continue
   mesh=UsdGeom.Mesh(prim);pts=Vt.Vec3fArray(mesh.GetPointsAttr().Get())
   if rootpath.endswith('Person'):
    assert cache.GetSkinningQuery(prim).ComputeSkinnedPoints(xforms,pts,0);vertices=np.array(pts)@sm[:3,:3]+sm[3,:3];person_points.append(vertices)
   else:
    m=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0));vertices=np.array(pts)@m[:3,:3]+m[3,:3]
   indices=mesh.GetFaceVertexIndicesAttr().Get();tris=[];offset=0
   for n in mesh.GetFaceVertexCountsAttr().Get():
    for k in range(1,n-1):tris.append([indices[offset],indices[offset+k],indices[offset+k+1]])
    offset+=n
   tri=vertices[np.array(tris)];objects.append((str(prim.GetPath()),tri[:,0],tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]))
 points=np.concatenate(person_points);assert abs(np.ptp(points[:,2])-placement['person_height_after_m'])<1e-8
 def first_hit(origin,direction):
  best=float('inf');path=None
  for name,v0,e1,e2 in objects:
   h=np.cross(direction,e2);a=np.einsum('ij,ij->i',e1,h);f=np.divide(1,a,out=np.zeros_like(a),where=np.abs(a)>1e-11);s=origin-v0;u=f*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=f*(q@direction);t=f*np.einsum('ij,ij->i',e2,q);ok=(np.abs(a)>1e-11)&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-5)
   if ok.any() and t[ok].min()<best:best=float(t[ok].min());path=name
  return best,path
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
 views={
 'main':dict(target=[0,-.10,1.48],direction=[1,-1.8,.7],width_m=1.65,resolution=[1800,1700]),
 'front':dict(target=[0,-.12,1.72],direction=[.7,-1.8,.65],width_m=.91,resolution=[1800,980]),
 'up':dict(target=[0,-.045,1.81],direction=[1,-1.8,.65],width_m=.76,resolution=[1000,1040]),
 'down':dict(target=[0,-.045,1.63],direction=[1,-1.8,.65],width_m=.76,resolution=[1000,1040])}
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
 write('external_views.json',views);write('render_status.json',dict(status='PASS',baseline_commit='a77f57b072c2dfcdb791f96a862ef0ddef041d13',scene='scenes/step2_1/indoor_wearer.usda',person_height_m=float(np.ptp(points[:,2])),camera_checks=camera_checks,external_frames=4,formal_sensor_frames=0,source_layers_saved=False,background='Office hidden in anonymous session layer; 650 dome + 1400 distant key; neutral dark material on device meshes for figure only',loading_status=list(context.get_stage_loading_status())))
except Exception as exc:
 write('render_status.json',{'status':'FAILED','error':str(exc),'traceback':traceback.format_exc()});raise
finally:app.close()
