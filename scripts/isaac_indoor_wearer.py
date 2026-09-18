"""One official indoor standing point, actual native RGB and renderer labels."""
import sys,json,hashlib,traceback,math,faulthandler,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));OUT=ROOT/'outputs/step2_1';OUT.mkdir(parents=True,exist_ok=True)
faulthandler.dump_traceback_later(90,repeat=True)
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','anti_aliasing':0,'multi_gpu':False,'sync_loads':False,'disable_viewport_updates':True,'extra_args':['--/app/asyncRendering=false']})
try:
 import numpy as np
 from PIL import Image
 from pxr import Usd,UsdGeom,UsdSkel,Semantics,Gf,Sdf,Vt
 import omni.usd,omni.timeline,omni.replicator.core as rep,carb
 from rig_common import load_config,camera_specs,geometry_specs,pixel_rays,camera_rotation,quat_wxyz
 cfg=json.loads((ROOT/'config/indoor_wearer_180.json').read_text());rig=load_config();cams=camera_specs(rig);sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
 timeline=omni.timeline.get_timeline_interface();settings=carb.settings.get_settings();settings.set('/rtx/post/aa/op',0);settings.set('/rtx/post/histogram/enabled',False);settings.set('/rtx/post/tonemap/filmIso',cfg['lighting']['film_iso'])
 def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2))
 write(OUT/'run_status.json',dict(status='RUNNING'))
 scene=ROOT/'scenes/step2_1/indoor_wearer.usda';scene.write_text('#usda 1.0\n(defaultPrim="World"\n metersPerUnit=1\n upAxis="Z"\n subLayers=[@../rig_v0.2.usda@,@character_pose.usda@])\n')
 omni.usd.get_context().open_stage(str(scene))
 for _ in range(12):app.update()
 stage=omni.usd.get_context().get_stage();room=UsdGeom.Xform.Define(stage,'/World/Room');room.GetPrim().GetReferences().AddReference(cfg['asset_root']+cfg['office_relative'])
 for i in range(200):
  app.update()
  if i%50==0:print('ROOM_LOADING',i,omni.usd.get_context().get_stage_loading_status(),flush=True)
 print('ROOM_REFERENCED',flush=True)
 def semantic(prim,name):
  api=Semantics.SemanticsAPI.Apply(prim,'Step21');api.CreateSemanticTypeAttr().Set('class');api.CreateSemanticDataAttr().Set(name)
 semantic(room.GetPrim(),'step21_environment');semantic(stage.GetPrimAtPath('/World/Person'),'step21_wearer')
 def triangles(prim,points=None):
  mesh=UsdGeom.Mesh(prim);pts=np.asarray(mesh.GetPointsAttr().Get() if points is None else points,dtype=float)
  if points is None:
   m=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode(0)));pts=pts@m[:3,:3]+m[3,:3]
  counts=mesh.GetFaceVertexCountsAttr().Get();indices=mesh.GetFaceVertexIndicesAttr().Get();ii=[];offset=0
  for n in counts:
   for k in range(1,n-1):ii.append([indices[offset],indices[offset+k],indices[offset+k+1]])
   offset+=n
  return pts[np.asarray(ii)]
 def hits(origin,direction,tris):
  e1=tris[:,1]-tris[:,0];e2=tris[:,2]-tris[:,0];h=np.cross(np.asarray(direction),e2);a=np.einsum('ij,ij->i',e1,h);safe=np.abs(a)>1e-12;f=np.divide(1,a,out=np.zeros_like(a),where=safe);s=np.asarray(origin)-tris[:,0];u=f*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=f*(q@np.asarray(direction));t=f*np.einsum('ij,ij->i',e2,q);return t[safe&(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)&(t>1e-8)]
 xy=cfg['person_xy_m'];floor_hits=[];ceiling_hits=[];bboxes=[]
 bc=UsdGeom.BBoxCache(Usd.TimeCode(0),['default','render'],useExtentsHint=False)
 for prim in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()):
  if not str(prim.GetPath()).startswith('/World/Room') or not prim.IsA(UsdGeom.Mesh):continue
  if UsdGeom.Imageable(prim).ComputeVisibility()=='invisible':continue
  box=bc.ComputeWorldBound(prim).ComputeAlignedRange();lo=np.array(box.GetMin());hi=np.array(box.GetMax())
  if lo[0]-.01<=xy[0]<=hi[0]+.01 and lo[1]-.01<=xy[1]<=hi[1]+.01:
   tr=triangles(prim)
   down=hits([*xy,.5],[0,0,-1],tr);up=hits([*xy,1.8],[0,0,1],tr)
   if len(down):floor_hits.append(dict(path=str(prim.GetPath()),z=.5-float(down.min())))
   if len(up):ceiling_hits.append(dict(path=str(prim.GetPath()),z=1.8+float(up.min())))
  if np.all(hi[:2]>np.array(xy)-.38) and np.all(lo[:2]<np.array(xy)+.38) and hi[2]>.08 and lo[2]<1.8:bboxes.append(dict(path=str(prim.GetPath()),bounds=[lo.tolist(),hi.tolist()]))
 assert floor_hits and ceiling_hits,'Need actual floor and overhead surface'
 floor=max(floor_hits,key=lambda a:a['z']);ceiling=min(ceiling_hits,key=lambda a:a['z']);print('FLOOR',floor,'CEILING',ceiling,'NEARBY',bboxes,flush=True)
 g=json.loads((ROOT/'reports/step2_1/character_geometry.json').read_text());scale=cfg['target_person_height_m']/g['height'];person_offset=np.array([*xy,floor['z']-g['bounds'][0][2]*scale])
 person=UsdGeom.Xformable(stage.GetPrimAtPath('/World/Person'));person.ClearXformOpOrder();person.AddTranslateOp().Set(Gf.Vec3d(*person_offset));person.AddScaleOp().Set(Gf.Vec3f(scale,scale,scale))
 cache=UsdSkel.Cache();skroot=next(UsdSkel.Root(p) for p in Usd.PrimRange(stage.GetPrimAtPath('/World/Person')) if p.IsA(UsdSkel.Root));skeleton=next(UsdSkel.Skeleton(p) for p in Usd.PrimRange(stage.GetPrimAtPath('/World/Person')) if p.IsA(UsdSkel.Skeleton));cache.Populate(skroot,Usd.PrimDefaultPredicate);query=cache.GetSkelQuery(skeleton);xforms=query.ComputeSkinningTransforms(Usd.TimeCode(0));skmatrix=np.array(UsdGeom.Xformable(skeleton).ComputeLocalToWorldTransform(Usd.TimeCode(0)));posed={};measured=[]
 for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/Person')):
  if not prim.IsA(UsdGeom.Mesh):continue
  pts=Vt.Vec3fArray(UsdGeom.Mesh(prim).GetPointsAttr().Get());sq=cache.GetSkinningQuery(prim);assert sq.ComputeSkinnedPoints(xforms,pts,Usd.TimeCode(0));arr=np.array(pts)@skmatrix[:3,:3]+skmatrix[3,:3];posed[prim.GetName()]=(prim,arr);measured.append(arr)
 allpoints=np.concatenate(measured);height=float(np.ptp(allpoints[:,2]));assert abs(height-1.8)<2e-6
 skinprim,skin=posed['trans__organic__malecaucasianskin'];skintris=triangles(skinprim,skin);mount_z=cfg['forehead_source_height_m']*scale+person_offset[2];cross=hits([xy[0],xy[1]-1,mount_z],[0,1,0],skintris);assert len(cross)>=2
 forehead=np.array([xy[0],xy[1]-1+cross.min(),mount_z]);back=np.array([xy[0],xy[1]-1+cross.max(),mount_z])
 # Back of fixed central housing is 30 mm behind B origin; only the whole rig moves.
 housing=rig['geometry']['central_housing'];back_offset=-(housing['center_mm'][0]-housing['size_mm'][0]/2)*.001
 rigpos=forehead+np.array([0,-(back_offset+cfg['forehead_housing_gap_m']),0]);R=np.array([[0,1,0],[-1,0,0],[0,0,1]],float)
 xf=UsdGeom.Xformable(stage.GetPrimAtPath('/World/Rig'));xf.ClearXformOpOrder();mat=Gf.Matrix4d(1);mat.SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1),cfg['rig_yaw_deg']));mat.SetTranslateOnly(Gf.Vec3d(*rigpos));xf.AddTransformOp().Set(mat)
 for group in ['Housing','Accessories','WearerMount']:UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/'+group)).GetVisibilityAttr().Set('inherited')
 UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/Wearer')).GetVisibilityAttr().Set('invisible')
 UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/Wearer/head_ellipsoid')).GetVisibilityAttr().Set('invisible')
 for obj in geometry_specs(rig):
  if obj['group']=='Wearer':continue
  semantic(stage.GetPrimAtPath('/World/Rig/'+obj['group']+'/'+obj['name']),('step21_mount_' if obj['group']=='WearerMount' else 'step21_device_')+obj['name'])
 camera_records=[]
 for cam in cams:
  prim=stage.GetPrimAtPath(cam['prim_path'].replace('/SevenCameraRig','/World/Rig'));m=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode(0)));pos=m[3,:3];forward=-m[2,:3];up=m[1,:3]
  assert np.allclose(pos,rigpos+R@(np.array(cam['position_mm'])*.001),atol=1e-7);assert np.allclose(forward,R@cam['forward_B']);assert np.allclose(up,R@cam['up_B']);assert np.allclose(m[:3,:3]@m[:3,:3].T,np.eye(3),atol=1e-7)
  assert abs(prim.GetAttribute('clippingRange').Get()[0]-.0001)<1e-10
  # Closed-head crossing parity on three generic rays; centers are all forward of forehead.
  counts=[len(np.unique(np.round(hits(pos,d,skintris),7))) for d in [[0,1,0],[1,.123,.217],[-.137,1,.271]]];assert sum(n%2 for n in counts)<2,(cam['id'],counts)
  camera_records.append(dict(camera_id=cam['id'],world_position_m=pos.tolist(),height_above_floor_m=float(pos[2]-floor['z']),forward_world=forward.tolist(),image_up_world=up.tolist(),skin_ray_crossing_counts=counts,projection=cam['optics']))
 # Sample actual scalp cross sections at headband height for fit evidence, no geometry adjustment.
 fit=[]
 for dz in [-.008,0,.008]:
  z=mount_z+dz;cross=hits([xy[0],xy[1]-1,z],[0,1,0],skintris)
  if len(cross):fit.append(dict(z=z,skin_front_y=xy[1]-1+float(cross.min()),skin_rear_y=xy[1]-1+float(cross.max()),rear_strap_inner_y=float(rigpos[1]+.210),rear_penetration_m=max(0.,xy[1]-1+float(cross.max())-(rigpos[1]+.210))))
 evidence=dict(config_sha256=sha,person_height_before_m=g['height'],uniform_person_scale=scale,person_height_after_m=height,person_translation_m=person_offset.tolist(),feet_world=allpoints[np.argmin(allpoints[:,2])].tolist(),head_top_world=allpoints[np.argmax(allpoints[:,2])].tolist(),height_method='evaluated UsdSkel skinned vertices including shoes and outer head, excluding device',floor=floor,ceiling=ceiling,nearby_object_bounds=bboxes,forehead_reference_world_m=forehead.tolist(),head_rear_reference_world_m=back.tolist(),forehead_method='first actual skinned head triangle intersection of +Y ray at x=0, source z=1.72 m',rig_translation_world_m=rigpos.tolist(),R_world_B=R.tolist(),rig_scale=1.,camera_records=camera_records,imu_world_position_m=(rigpos+R@(np.array(rig['layout']['imu_position_mm'])*.001)).tolist(),imu_height_above_floor_m=float(rigpos[2]-floor['z']),headband_fit_samples=fit,original_ellipsoid_visibility='invisible',standing_pose=g['pose_changes'],lighting=cfg['lighting'])
 write(OUT/'placement.json',evidence);print('PLACEMENT',json.dumps(evidence),flush=True)
 timeline.pause();timeline.set_current_time(0.)
 stage.GetRootLayer().Save()
 for _ in range(100):app.update()
 def render(path,resolution,labels=True):
  prod=rep.create.render_product(path,tuple(resolution));rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([prod]);seg=None
  if labels:seg=rep.AnnotatorRegistry.get_annotator('instance_segmentation',init_params={'colorize':False});seg.attach([prod])
  for _ in range(12):app.update()
  timeline.pause();timeline.set_current_time(0.);rep.orchestrator.step(rt_subframes=16,delta_time=0.,pause_timeline=True)
  arr=np.array(rgb.get_data())[...,:3].copy();data=seg.get_data() if seg else None
  if data:data={'data':np.array(data['data']).copy(),'info':data['info']}
  rgb.detach([prod])
  if seg:seg.detach([prod])
  prod.destroy();assert arr.shape[:2]==tuple(resolution[::-1]);assert timeline.get_current_time()==0.;return arr,data
 def setmode(mode):
  UsdGeom.Imageable(stage.GetPrimAtPath('/World/Person')).GetVisibilityAttr().Set('inherited' if mode=='worn_full' else 'invisible')
  for group in ['Housing','Accessories','WearerMount']:UsdGeom.Imageable(stage.GetPrimAtPath('/World/Rig/'+group)).GetVisibilityAttr().Set('invisible' if mode=='room_only' else 'inherited')
 summary=[]
 for mode in cfg['mode_order']:
  setmode(mode);directory=OUT/mode;directory.mkdir(exist_ok=True)
  for cam in cams:
   arr,data=render(cam['prim_path'].replace('/SevenCameraRig','/World/Rig'),cam['optics']['resolution']);_,valid=pixel_rays(cam);labels=data['data'];assert labels.shape==valid.shape;classes=np.full(valid.shape,5,np.uint8);mapped={}
   for key,labelpath in data['info']['idToLabels'].items():
    semantics=data['info'].get('idToSemantics',{}).get(str(key),{}).get('class','').lower();labelpath=str(labelpath)
    code=5
    if labelpath.startswith('/World/Rig/WearerMount') or 'step21_mount_' in semantics:code=2
    elif labelpath.startswith('/World/Rig/Housing') or labelpath.startswith('/World/Rig/Accessories') or 'step21_device_' in semantics:code=1
    elif labelpath.startswith('/World/Person') or 'step21_wearer' in semantics:code=3
    elif labelpath.startswith('/World/Room') or 'step21_environment' in semantics:code=4
    classes[labels==int(key)]=code;mapped[str(key)]=dict(usd_path=labelpath,semantics=semantics,class_code=code,valid_pixels=int(((labels==int(key))&valid).sum()))
   classes[~valid]=0;Image.fromarray(arr).save(directory/(cam['id']+'_raw.png'));masked=arr.copy();masked[~valid]=0;Image.fromarray(masked).save(directory/(cam['id']+'.png'));Image.fromarray(classes).save(directory/(cam['id']+'_classes.png'));Image.fromarray(valid.astype(np.uint8)*255).save(directory/(cam['id']+'_valid.png'));np.savez_compressed(directory/(cam['id']+'_labels.npz'),renderer_instance_id=labels,classes=classes,valid=valid)
   write(directory/(cam['id']+'_labels.json'),dict(raw_info=data['info'],mapping=mapped))
   counts={name:int((classes==code).sum()) for name,code in cfg['class_codes'].items()};nv=int(valid.sum());entry=dict(camera_id=cam['id'],mode=mode,N_valid=nv,counts=counts,ratios={k:v/nv for k,v in counts.items() if k!='INVALID'});summary.append(entry)
   write(directory/(cam['id']+'.json'),dict(camera_id=cam['id'],mode=mode,resolution=cam['optics']['resolution'],projection=cam['optics'],config_sha256=sha,placement=camera_records[int(cam['id'][1])],time_seconds=0.,isaac_version='6.0.1.0',same_render_product_rgb_labels=True,lighting=cfg['lighting'],execution='static sequential RTX; no 30 FPS claim',original_ellipsoid_hidden=True))
   print('CAPTURE',cam['id'],mode,counts,flush=True)
  write(OUT/'occlusion_summary.json',summary)
  if mode=='worn_full':print('FIRST_WORN_SEVEN_READY',flush=True)
 setmode('worn_full')
 # External inspection cameras, no markers inserted into sensor views.
 overview=OUT/'overview';overview.mkdir(exist_ok=True)
 views={'full_body':([2.6,-3.8,1.9],[0,0,1.05],(1600,1200),32.),'front_close':([0,-.72,mount_z+.035],rigpos,(1600,1200),55.),'left_close':([.52,-.20,mount_z+.06],rigpos+np.array([0,.09,0]),(1600,1200),55.),'right_close':([-.52,-.20,mount_z+.06],rigpos+np.array([0,.09,0]),(1600,1200),55.)}
 for name,(pos,target,res,focal) in views.items():
  pos=np.array(pos);target=np.array(target);rot=camera_rotation(target-pos,[0,0,1]);q=quat_wxyz(rot@np.diag([1.,-1.,-1.]));cam=UsdGeom.Camera.Define(stage,'/World/External/'+name);cam.AddTranslateOp().Set(Gf.Vec3d(*pos));cam.AddOrientOp().Set(Gf.Quatf(q[0],Gf.Vec3f(*q[1:])));cam.CreateHorizontalApertureAttr(36.);cam.CreateVerticalApertureAttr(27.);cam.CreateFocalLengthAttr(focal);cam.CreateClippingRangeAttr(Gf.Vec2f(.0001,100.));cam.CreateFStopAttr(0.)
  arr,_=render(str(cam.GetPath()),res,False);Image.fromarray(arr).save(overview/(name+'_raw.png'));write(overview/(name+'.json'),dict(position_world_m=pos.tolist(),R_world_optical=rot.tolist(),resolution=res,fx_px=res[0]*focal/36,fy_px=res[1]*focal/27))
 stage.GetRootLayer().Save()
 # Inventory composed source layers and unresolved payloads, preserving source paths rather than packaging assets.
 layers=[l.identifier for l in stage.GetUsedLayers() if not l.anonymous];write(ROOT/'reports/step2_1/loaded_layers.json',layers)
 write(OUT/'run_status.json',dict(status='CAPTURED_REVIEW_REQUIRED',captures=21,external_views=4,config_sha256=sha,person_height_m=height,stage_loading_status=list(omni.usd.get_context().get_stage_loading_status())))
except Exception as exc:
 traceback.print_exc();write(OUT/'run_status.json',dict(status='FAILED',error=str(exc),traceback=traceback.format_exc()));raise
finally:
 faulthandler.cancel_dump_traceback_later();app.close()
