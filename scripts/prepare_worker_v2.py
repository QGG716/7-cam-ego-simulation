"""Evaluate a standing official worker and author a new scene, source layers read-only."""
import sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'reports/step2_1b_v2';SCENE=ROOT/'scenes/step2_1b_v2';CONF=ROOT/'config/step2_1b_v2'
for p in [OUT,SCENE,CONF,ROOT/'.cache/step2_1b_v2']:p.mkdir(parents=True,exist_ok=True)
def write(p,d):p.write_text(json.dumps(d,indent=2))
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','multi_gpu':False,'sync_loads':False})
try:
 import numpy as np
 from pxr import Usd,UsdGeom,UsdSkel,Gf,Vt,Sdf
 from scipy.spatial import ConvexHull
 from rig_common import load_config,camera_specs
 from fit_geometry_v2 import audit,surface_crossings
 discovery=json.loads((OUT/'worker_discovery.json').read_text());selected='original_male_adult_construction_01';source=discovery[selected]['url']
 source_stage=Usd.Stage.Open(source);assert UsdGeom.GetStageUpAxis(source_stage)=='Z';assert UsdGeom.GetStageMetersPerUnit(source_stage)==1
 path=SCENE/'worker_pose.usda';stage=Usd.Stage.CreateNew(str(path)) if not path.exists() else Usd.Stage.Open(str(path));stage.GetRootLayer().Clear()
 UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1.)
 world=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(world.GetPrim());person=UsdGeom.Xform.Define(stage,'/World/Person');person.GetPrim().GetReferences().AddReference(source)
 root=next(UsdSkel.Root(p) for p in stage.Traverse() if p.IsA(UsdSkel.Root));skeleton=next(UsdSkel.Skeleton(p) for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton));cache=UsdSkel.Cache();cache.Populate(root,Usd.PrimDefaultPredicate)
 query=cache.GetSkelQuery(skeleton);joints=list(skeleton.GetJointsAttr().Get());local=list(skeleton.GetRestTransformsAttr().Get());global_t=list(query.ComputeJointSkelTransforms(0));parents=UsdSkel.Topology(joints).GetParentIndices();changes=[]
 for side in ['L','R']:
  i=next(i for i,j in enumerate(joints) if j.endswith('/'+side+'_Upperarm'));child=next(i for i,j in enumerate(joints) if j.endswith('/'+side+'_Forearm'))
  vector=global_t[child].ExtractTranslation()-global_t[i].ExtractTranslation();angle=82. if vector[0]>0 else -82.
  rot=Gf.Matrix4d(1);rot.SetRotate(Gf.Rotation(Gf.Vec3d(0,1,0),angle));desired=global_t[i]*rot;desired.SetTranslateOnly(global_t[i].ExtractTranslation());local[i]=desired*global_t[parents[i]].GetInverse();changes.append({'joint':joints[i],'rotation_skeleton_Y_deg':angle})
 translations,rotations,scales=UsdSkel.DecomposeTransforms(Vt.Matrix4dArray(local));anim=UsdSkel.Animation.Define(stage,'/World/Person/StaticStandingPose');anim.CreateJointsAttr(joints);anim.CreateTranslationsAttr(translations);anim.CreateRotationsAttr(rotations);anim.CreateScalesAttr(scales);UsdSkel.BindingAPI.Apply(skeleton.GetPrim()).CreateAnimationSourceRel().SetTargets([anim.GetPath()])
 def extract(stage,prefix):
  skcache=UsdSkel.Cache();skroots=[UsdSkel.Root(p) for p in Usd.PrimRange(stage.GetPrimAtPath(prefix)) if p.IsA(UsdSkel.Root)];skels=[UsdSkel.Skeleton(p) for p in Usd.PrimRange(stage.GetPrimAtPath(prefix)) if p.IsA(UsdSkel.Skeleton)]
  for sr in skroots:skcache.Populate(sr,Usd.PrimDefaultPredicate)
  if skels:
   sk=skels[0];trans=skcache.GetSkelQuery(sk).ComputeSkinningTransforms(0);sm=np.array(UsdGeom.Xformable(sk).ComputeLocalToWorldTransform(0))
  result={};verts={}
  for p in Usd.PrimRange(stage.GetPrimAtPath(prefix)):
   if not p.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(p).ComputeVisibility()=='invisible':continue
   mesh=UsdGeom.Mesh(p);pts=Vt.Vec3fArray(mesh.GetPointsAttr().Get());sq=skcache.GetSkinningQuery(p)
   if sq and sq.HasJointInfluences():
    assert not sq.HasBlendShapes();assert sq.ComputeSkinnedPoints(trans,pts,0);m=sm
   else:m=np.array(UsdGeom.Xformable(p).ComputeLocalToWorldTransform(0))
   vertices=np.array(pts)@m[:3,:3]+m[3,:3];indices=mesh.GetFaceVertexIndicesAttr().Get();tri=[];offset=0
   for n in mesh.GetFaceVertexCountsAttr().Get():
    for k in range(1,n-1):tri.append([indices[offset],indices[offset+k],indices[offset+k+1]])
    offset+=n
   result[str(p.GetPath())]=vertices[np.array(tri)];verts[str(p.GetPath())]=vertices
  return result,verts
 body,vertices=extract(stage,'/World/Person');allp=np.concatenate(list(vertices.values()))
 skinpaths=[p for p in vertices if 'skin' in p.lower()];assert skinpaths, list(vertices)
 skin=np.concatenate([vertices[p] for p in skinpaths]);headtop=float(skin[:,2].max());foot=float(allp[:,2].min());height=headtop-foot;scale=1.8/height
 floor=json.loads((ROOT/'outputs/step2_1/placement.json').read_text())['floor'];original=person.GetLocalTransformation();sc=Gf.Matrix4d(1);sc.SetScale(Gf.Vec3d(scale,scale,scale));tr=Gf.Matrix4d(1);tr.SetTranslate(Gf.Vec3d(0,0,floor['z']-foot*scale));person.ClearXformOpOrder();person.AddTransformOp(opSuffix='normalized').Set(original*sc*tr)
 body,vertices=extract(stage,'/World/Person');allp=np.concatenate(list(vertices.values()));skin=np.concatenate([vertices[p] for p in skinpaths]);heightfinal=float(skin[:,2].max()-allp[:,2].min());assert abs(heightfinal-1.8)<1e-7
 stage.GetRootLayer().Save()
 measurement=dict(source=source,source_units_m=1,source_up='Z',source_forward='-Y',pose_changes=changes,skin_meshes=skinpaths,height_method='Final UsdSkel.ComputeSkinnedPoints: shoe minimum Z to actual skin head maximum Z; exclude helmet and rig from anthropometric height, include all attachments in fit',original_height_m=height,uniform_scale=scale,final_height_m=heightfinal,overall_person_with_attachments_height_m=float(np.ptp(allp[:,2])),meshes=[dict(path=p,vertices=len(v),triangles=len(body[p]),bounds=[v.min(0).tolist(),v.max(0).tolist()]) for p,v in vertices.items()])
 write(OUT/'worker_measurement.json',measurement);print('WORKER_MEASURED',json.dumps(measurement),flush=True)
 path=SCENE/'indoor_worker.usda';scene=Usd.Stage.CreateNew(str(path)) if not path.exists() else Usd.Stage.Open(str(path));scene.GetRootLayer().Clear();scene.GetRootLayer().subLayerPaths=['../rig_v0.2.usda','worker_pose.usda'];UsdGeom.SetStageUpAxis(scene,'Z');UsdGeom.SetStageMetersPerUnit(scene,1.);scene.SetDefaultPrim(scene.GetPrimAtPath('/World'))
 UsdGeom.Xform.Define(scene,'/World/Room').GetPrim().GetReferences().AddReference(json.loads((ROOT/'reports/step2_1/asset_probe.json').read_text())['assets']['office']['url'])
 UsdGeom.Imageable(scene.GetPrimAtPath('/World/Rig/Wearer')).CreateVisibilityAttr('invisible')
 old=json.loads((ROOT/'outputs/step2_1/placement.json').read_text());R=np.array(old['R_world_B']);t=np.array(old['rig_translation_world_m']);rig=UsdGeom.Xformable(scene.GetPrimAtPath('/World/Rig'))
 def place(t):
  m=np.eye(4);m[:3,:3]=R.T;m[3,:3]=t;rig.ClearXformOpOrder();rig.AddTransformOp().Set(Gf.Matrix4d(m.tolist()))
 place(t);objects,_=extract(scene,'/World/Rig');before=json.loads((OUT/'fit_before.json').read_text()) if (OUT/'fit_before.json').exists() else audit(objects,body);write(OUT/'fit_before.json',before);print('FIT_BEFORE',json.dumps(before),flush=True)
 # After worker substitution, fixed housing/cable can require a small whole-rig translation.
 fixed={p:a for p,a in objects.items() if '/WearerMount/' not in p};bodytri=np.concatenate(list(body.values()));attempts=[]
 # Discrete mounting corrections to clear the rigid cable around the helmet edge.
 # These are fit checks only, with no camera-layout or FOV objective.
 candidates_mm=[[0,0,0],[0,-20,-20],[-15,-20,-15],[-25,-40,0],[-30,-50,0],[-25,-35,-20],[-25,-30,-30],[-25,-20,-40],[-30,-55,-10],[-35,-55,0]]
 for candidate in candidates_mm:
  delta=np.array(candidate)/1000;collisions=[]
  for name,tri in fixed.items():
   moved=tri+delta;near=bodytri[np.all(bodytri.max(1)>=moved.min((0,1)),axis=1)&np.all(bodytri.min(1)<=moved.max((0,1)),axis=1)]
   if len(near):
    hits,_=surface_crossings(moved,near)
    if hits:collisions.append(name)
  attempts.append(dict(translation_delta_world_mm=candidate,intersecting_fixed_parts=collisions));print('FIT_TRIAL',attempts[-1],flush=True)
  if not collisions:break
 write(OUT/'rigid_fit_trials.json',attempts)
 if collisions:raise RuntimeError('Selected small rigid mounting corrections cannot clear frozen hardware; see rigid_fit_trials')
 t=t+delta;place(t)
 # Convex 2-D envelope of every actual triangle crossing the entire band height.
 # The convex envelope is conservative for hair/PPE, not a replacement collision mesh.
 zlo=t[2]-.008;zhi=t[2]+.008;bandtri=bodytri[(bodytri.max(1)[:,2]>=zlo)&(bodytri.min(1)[:,2]<=zhi)]
 pts=(bandtri.reshape(-1,3)-t)@R;xy=pts[:,:2];hull=ConvexHull(xy);poly=xy[hull.vertices]
 # Support-line offset, 1 mm clearance + 5 mm band thickness. Front cutoff at back housing face.
 def offset_poly(poly,dist):
  edges=np.roll(poly,-1,axis=0)-poly;n=np.column_stack((edges[:,1],-edges[:,0]));n/=np.linalg.norm(n,axis=1)[:,None];b=np.einsum('ij,ij->i',n,poly)+dist
  return np.array([np.linalg.solve(np.stack([n[i-1],n[i]]),[b[i-1],b[i]]) for i in range(len(poly))])
 inner=offset_poly(poly,.001);outer=offset_poly(poly,.006)
 # Closed contour includes forehead support. Connect the front of contour to housing rear by an actual padded bridge.
 def mesh_ring(name,inner,outer):
  n=len(inner);p=np.vstack([np.column_stack((a,np.full(n,z))) for z in [-.008,.008] for a in [inner,outer]]);faces=[]
  for i in range(n):
   j=(i+1)%n;faces.extend([[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],[i,2*n+i,2*n+j,j],[n+i,n+j,3*n+j,3*n+i]])
  mesh=UsdGeom.Mesh.Define(scene,name);mesh.CreatePointsAttr(Vt.Vec3fArray(p.tolist()));mesh.CreateFaceVertexCountsAttr([4]*len(faces));mesh.CreateFaceVertexIndicesAttr(np.array(faces).reshape(-1).tolist());mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDisplayColorAttr([Gf.Vec3f(.07,.09,.12)])
 def box(name,lo,hi):
  p=np.array([[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]]);faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]]
  m=UsdGeom.Mesh.Define(scene,name);m.CreatePointsAttr(Vt.Vec3fArray(p.tolist()));m.CreateFaceVertexCountsAttr([4]*6);m.CreateFaceVertexIndicesAttr(np.array(faces).reshape(-1).tolist());m.CreateSubdivisionSchemeAttr('none');m.CreateDisplayColorAttr([Gf.Vec3f(.09,.11,.14)])
 for name in ['strap_left','strap_right','strap_rear','strap_left_bracket']:scene.GetPrimAtPath('/World/Rig/WearerMount/'+name).SetActive(False)
 mesh_ring('/World/Rig/WearerMount/FittedBand',inner,outer)
 # A central front bridge between the ring's foremost support and rear housing face.
 # Fit tested against real body afterwards; ring joins are mechanically overlapping by <1 mm.
 front=float(outer[:,0].max());box('/World/Rig/WearerMount/ForeheadBridge',[front-.002,-.012,-.007],[-.030,.012,.007])
 scene.GetRootLayer().Save();objects,_=extract(scene,'/World/Rig');after=audit(objects,body);write(OUT/'fit_after.json',after)
 passed=not any(a.get('triangle_crossings',0) or a.get('human_vertices_inside_solid',0) for a in after)
 placement=dict(worker=measurement,rig_translation_before_m=old['rig_translation_world_m'],rig_translation_world_m=t.tolist(),R_world_B=R.tolist(),rig_scale=1.,translation_delta_world_m=(t-np.array(old['rig_translation_world_m'])).tolist(),rotation_delta_deg=[0,0,0],translation_reason='Only after fixed hardware collisions remained, move complete rig forward; camera and fixed hardware relative transforms unchanged',fixed_part_trials=attempts,floor=floor,config_sha256=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest(),camera_records=[dict(camera_id=c['id'],world_position_m=(t+R@np.array(c['position_mm'])/1000).tolist(),height_above_floor_m=float(t[2]+c['position_mm'][2]/1000-floor['z']),forward_world=(R@c['forward_B']).tolist(),image_up_world=(R@c['up_B']).tolist(),projection=c['optics']) for c in camera_specs(load_config())],mount=dict(original=load_config()['geometry'],replacement='closed conservative convex band and connected forehead bridge',band_inner_B_xy_m=inner.tolist(),band_outer_B_xy_m=outer.tolist(),band_height_m=.016,nominal_min_clearance_m=.001,thickness_m=.005),fit_status='PASS' if passed else 'FAIL')
 write(CONF/'final_placement.json',placement);write(OUT/'prepare_status.json',dict(status='PASS',worker_asset_and_height='PASS',wearer_fit=placement['fit_status'],actual_person_meshes=len(body),actual_device_and_mount_meshes=len(objects)))
 np.savez_compressed(ROOT/'.cache/step2_1b_v2/evaluated_meshes.npz',**{('body'+str(i)):v for i,v in enumerate(body.values())},**{('rig'+str(i)):v for i,v in enumerate(objects.values())})
 print('FINAL',json.dumps(placement),flush=True)
except Exception as e:
 write(OUT/'prepare_status.json',{'status':'FAILED','error':str(e),'traceback':traceback.format_exc()});raise
finally:app.close()
