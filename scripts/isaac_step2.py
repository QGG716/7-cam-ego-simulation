"""Actual Step 2 RTX capture; never writes Step 1 layers or outputs."""
import sys,json,hashlib,traceback,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'outputs/step2';OUT.mkdir(parents=True,exist_ok=True)
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','anti_aliasing':0,'multi_gpu':False})
try:
 import numpy as np
 from PIL import Image
 from pxr import Usd,UsdGeom,UsdShade,Semantics,Sdf,Gf
 import omni.usd,omni.timeline,omni.replicator.core as rep,carb
 from rig_common import load_config,camera_specs,pixel_rays,nearest_hit
 from analyze_step2 import components,OPTIONS,SHA
 from projection import project
 c=load_config();cams=camera_specs(c);objs=components();timeline=omni.timeline.get_timeline_interface()
 settings=carb.settings.get_settings();settings.set('/rtx/post/aa/op',0);settings.set('/rtx/post/histogram/enabled',False);settings.set('/rtx/post/tonemap/filmIso',100.)
 def write(path,value):path.write_text(json.dumps(value,indent=2))
 def open_scene(name,layer):
  path=ROOT/'scenes/step2'/name;path.parent.mkdir(exist_ok=True,parents=True)
  path.write_text('#usda 1.0\n(defaultPrim="World"\n metersPerUnit=1\n upAxis="Z"\n subLayers=[@../'+layer+'@])\n')
  omni.usd.get_context().open_stage(str(path))
  for _ in range(12):app.update()
  stage=omni.usd.get_context().get_stage();timeline.pause();timeline.set_current_time(0.);return stage
 def mode(stage,value):
  for group in OPTIONS['modes']['worn']:
   UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/'+group)).GetVisibilityAttr().Set('inherited' if group in OPTIONS['modes'][value] else 'invisible')
 def semantic(prim,name):
  api=Semantics.SemanticsAPI.Apply(prim,'Step2');api.CreateSemanticTypeAttr().Set('class');api.CreateSemanticDataAttr().Set(name)
 def render(cam):
  product=rep.create.render_product(cam['prim_path'].replace('/SevenCameraRig','/World/Rig'),tuple(cam['optics']['resolution']))
  rgb=rep.AnnotatorRegistry.get_annotator('rgb');seg=rep.AnnotatorRegistry.get_annotator('instance_segmentation',init_params={'colorize':False})
  rgb.attach([product]);seg.attach([product])
  for _ in range(8):app.update()
  timeline.pause();timeline.set_current_time(0.);rep.orchestrator.step(rt_subframes=8,delta_time=0.,pause_timeline=True)
  arr=np.asarray(rgb.get_data())[...,:3].copy();data=seg.get_data();labels=np.asarray(data['data']).copy();info=data['info']
  assert arr.shape[:2]==labels.shape==tuple(cam['optics']['resolution'][::-1]);assert timeline.get_current_time()==0.
  rgb.detach([product]);seg.detach([product]);product.destroy();return arr,labels,info
 stage=open_scene('inspection.usda','inspection_scene.usda')
 assert UsdGeom.GetStageMetersPerUnit(stage)==1
 geometry=[]
 for obj in objs:
  prim=stage.GetPrimAtPath(obj['usd_path']);assert prim.IsA(UsdGeom.Mesh)
  mesh=UsdGeom.Mesh(prim);points=np.array(mesh.GetPointsAttr().Get(),float)
  matrix=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
  pts=(np.array([matrix.Transform(Gf.Vec3d(*p)) for p in points])-c['simulation']['rig_world_translation_m'])*1000
  center=(np.array(obj['a_mm'])+obj['b_mm'])/2 if obj['kind']=='cylinder' else np.array(obj['center_mm'])
  vec=pts-center;dist=np.linalg.norm(vec,axis=1);nonzero=dist>1e-8
  with np.errstate(invalid='ignore'):expected=nearest_hit(center,vec[nonzero]/dist[nonzero,None],obj)
  residual=float(np.max(np.abs(expected-dist[nonzero])))
  # Every vertex lies on the analytic surface; face centers measure inward chord approximation.
  counts=np.array(mesh.GetFaceVertexCountsAttr().Get());indices=np.array(mesh.GetFaceVertexIndicesAttr().Get());faces=[];offset=0
  for n in counts:faces.append(pts[indices[offset:offset+n]].mean(axis=0));offset+=n
  vec=np.array(faces)-center;dist=np.linalg.norm(vec,axis=1);nz=dist>1e-8
  with np.errstate(invalid='ignore'):gap=nearest_hit(center,vec[nz]/dist[nz,None],obj)-dist[nz]
  assert residual<.001,(obj['name'],residual)
  geometry.append(dict(component_id=obj['id'],name=obj['name'],group=obj['group'],usd_path=obj['usd_path'],vertex_count=len(points),face_count=len(counts),vertex_surface_max_error_mm=residual,face_center_max_inward_chord_gap_mm=float(max(gap)),mesh_bounds_B_mm=[pts.min(axis=0).tolist(),pts.max(axis=0).tolist()],double_sided=mesh.GetDoubleSidedAttr().Get()))
  semantic(prim,obj['name'])
 write(OUT/'geometry_verification.json',dict(status='PASS',units='USD m converted once to B mm; analytic mm',components=geometry))
 runtime=[]
 for cam in cams:
  prim=stage.GetPrimAtPath(cam['prim_path'].replace('/SevenCameraRig','/World/Rig'))
  assert np.allclose(prim.GetAttribute('xformOp:translate').Get(),np.array(cam['position_mm'])*.001,atol=1e-10)
  q=prim.GetAttribute('xformOp:orient').Get();assert np.allclose([q.GetReal(),*q.GetImaginary()],cam['q_B_usd_wxyz'])
  assert prim.GetAttribute('sim:configSha256').Get()==SHA
  assert abs(prim.GetAttribute('clippingRange').Get()[0]-.0001)<1e-10
  runtime.append(dict(camera_id=cam['id'],schemas=list(prim.GetAppliedSchemas()),attributes={str(a.GetName()):str(a.Get()) for a in prim.GetAttributes() if any(k in str(a.GetName()) for k in ['ftheta','lensdistortion','clippingRange'])}))
 write(OUT/'runtime_cameras.json',runtime)
 for mode_name in OPTIONS['modes']:
  mode(stage,mode_name)
  for cam in cams:
   arr,seg,info=render(cam);_,valid=pixel_rays(cam);directory=OUT/mode_name;directory.mkdir(exist_ok=True)
   Image.fromarray(arr).save(directory/(cam['id']+'_raw.png'));masked=arr.copy();masked[~valid]=0;Image.fromarray(masked).save(directory/(cam['id']+'.png'))
   ids=np.zeros(seg.shape,np.uint16);mapping=info['idToLabels']
   for label,path in mapping.items():
    for obj in objs:
     if str(path)==obj['usd_path'] or (not str(path) and info.get('idToSemantics',{}).get(str(label),{}).get('class','').lower()==obj['name'].lower()):ids[seg==int(label)]=obj['id']
   np.savez_compressed(directory/(cam['id']+'_rtx.npz'),renderer_instance_id=seg,component_id=ids,valid=valid,blocked=(ids>0)&valid)
   write(directory/(cam['id']+'_labels.json'),info)
   visibility={g:UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/'+g)).ComputeVisibility() for g in OPTIONS['modes']['worn']}
   write(directory/(cam['id']+'.json'),dict(camera_id=cam['id'],mode=mode_name,resolution=cam['optics']['resolution'],projection=cam['optics'],config_sha256=SHA,scene='scenes/step2/inspection.usda',scene_state=visibility,simulation_time_seconds=timeline.get_current_time(),isaac_version='6.0.1.0',execution='static sequential RayTracedLighting; RGB + instance_segmentation same RenderProduct',raw_label_source='RTX instance_segmentation; mapped by exact USD path or unique semantic name when path empty',rgb_label_same_resolution=True))
   print('CAPTURE',mode_name,cam['id'],'mapped pixels',int(((ids>0)&valid).sum()),flush=True)
 mode(stage,'worn');stage.GetRootLayer().Save()
 # Independent white target registration confirms RGB/labels share the >90 degree projection.
 stage=open_scene('label_projection.usda','rig_v0.2.usda');mode(stage,'ideal')
 mat=UsdShade.Material.Define(stage,'/World/White');shader=UsdShade.Shader.Define(stage,'/World/White/Shader');shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('emissiveColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1,1,1));mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
 sphere=UsdGeom.Sphere.Define(stage,'/World/RegistrationTarget');sphere.CreateRadiusAttr(.006);op=sphere.AddTranslateOp();semantic(sphere.GetPrim(),'registration_target');UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(mat)
 checks=[];directory=OUT/'label_projection';directory.mkdir(exist_ok=True)
 for cid,theta in [('C0',0),('C1',75),('C3',95),('C3',105),('C4',105),('C5',105),('C6',105)]:
  cam=next(x for x in cams if x['id']==cid);t=math.radians(theta);ray=np.array([math.sin(t),0,math.cos(t)])
  pos=np.array(cam['position_mm'])*.001+np.array(c['simulation']['rig_world_translation_m'])+np.array(cam['R_B_optical'])@ray;op.Set(Gf.Vec3d(*pos))
  arr,seg,info=render(cam);mask=np.zeros(seg.shape,bool)
  for label,path in info['idToLabels'].items():
   if str(path)=='/World/RegistrationTarget' or info.get('idToSemantics',{}).get(str(label),{}).get('class')=='registration_target':mask|=seg==int(label)
  signal=arr.mean(axis=2)>80
  def centroid(m):
   y,x=np.where(m);return [float(x.mean()+.5),float(y.mean()+.5)] if len(x) else None
  rgbuv=centroid(signal);labeluv=centroid(mask);error=float(np.linalg.norm(np.array(rgbuv)-labeluv)) if rgbuv and labeluv else None
  uv=project(cam,ray)[0];projection_error=float(np.linalg.norm(np.array(labeluv)-uv)) if labeluv else None
  row=dict(camera_id=cid,off_axis_deg=theta,rgb_centroid=rgbuv,label_centroid=labeluv,centroid_difference_px=error,label_projection_error_px=projection_error,rgb_pixels=int(signal.sum()),label_pixels=int(mask.sum()),status='PASS' if error is not None and error<=2 and projection_error<=2 else 'FAIL')
  checks.append(row);key=cid+'_'+str(theta);Image.fromarray(arr).save(directory/(key+'_rgb.png'));Image.fromarray(mask.astype(np.uint8)*255).save(directory/(key+'_label.png'));write(directory/(key+'.json'),info)
  print('LABEL_PROJECTION',row,flush=True)
 sphere.GetVisibilityAttr().Set('invisible');stage.GetRootLayer().Save();write(OUT/'label_projection_checks.json',checks)
 write(OUT/'render_status.json',dict(status='PASS' if all(r['status']=='PASS' for r in checks) else 'NEEDS_REVIEW',captures=21,config_sha256=SHA,label_projection_checks=checks))
except Exception as exc:
 traceback.print_exc();(OUT/'render_status.json').write_text(json.dumps(dict(status='FAILED',error=str(exc),traceback=traceback.format_exc()),indent=2));raise
finally:app.close()
