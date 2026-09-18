"""Minimal authored standing pose and measured skinned geometry, source assets read-only."""
import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','multi_gpu':False})
try:
 import numpy as np
 from pxr import Usd,UsdGeom,UsdSkel,Gf,Vt
 data=json.loads((ROOT/'reports/step2_1/asset_probe.json').read_text());source=data['assets']['doctor']['url']
 path=ROOT/'scenes/step2_1/character_pose.usda';path.parent.mkdir(parents=True,exist_ok=True)
 stage=Usd.Stage.CreateNew(str(path)) if not path.exists() else Usd.Stage.Open(str(path));stage.GetRootLayer().Clear()
 UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1.)
 world=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(world.GetPrim());person=UsdGeom.Xform.Define(stage,'/World/Person');person.GetPrim().GetReferences().AddReference(source)
 root=next(UsdSkel.Root(p) for p in stage.Traverse() if p.IsA(UsdSkel.Root));skeleton=next(UsdSkel.Skeleton(p) for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton));cache=UsdSkel.Cache();cache.Populate(root,Usd.PrimDefaultPredicate)
 query=cache.GetSkelQuery(skeleton);joints=list(skeleton.GetJointsAttr().Get());local=list(skeleton.GetRestTransformsAttr().Get());global_t=list(query.ComputeJointSkelTransforms(Usd.TimeCode(0)))
 topo=UsdSkel.Topology(joints);parents=topo.GetParentIndices();changes=[]
 for side in ['L','R']:
  i=next(i for i,j in enumerate(joints) if j.endswith('/'+side+'_Upperarm'));child=next(i for i,j in enumerate(joints) if j.endswith('/'+side+'_Forearm'))
  vector=global_t[child].ExtractTranslation()-global_t[i].ExtractTranslation();angle=82. if vector[0]>0 else -82.
  rotation=Gf.Matrix4d(1);rotation.SetRotate(Gf.Rotation(Gf.Vec3d(0,1,0),angle));desired=global_t[i]*rotation;desired.SetTranslateOnly(global_t[i].ExtractTranslation());local[i]=desired*global_t[parents[i]].GetInverse();changes.append({'joint':joints[i],'rotation_skeleton_Y_deg':angle})
 translations,rotations,scales=UsdSkel.DecomposeTransforms(Vt.Matrix4dArray(local));anim=UsdSkel.Animation.Define(stage,'/World/Person/StaticStandingPose');anim.CreateJointsAttr(joints);anim.CreateTranslationsAttr(translations);anim.CreateRotationsAttr(rotations);anim.CreateScalesAttr(scales);UsdSkel.BindingAPI.Apply(skeleton.GetPrim()).CreateAnimationSourceRel().SetTargets([anim.GetPath()])
 cache.Clear();cache.Populate(root,Usd.PrimDefaultPredicate);query=cache.GetSkelQuery(skeleton);skintrans=query.ComputeSkinningTransforms(Usd.TimeCode(0));records=[];arrays={}
 for p in stage.Traverse():
  if not p.IsA(UsdGeom.Mesh):continue
  mesh=UsdGeom.Mesh(p);points=Vt.Vec3fArray(mesh.GetPointsAttr().Get());sq=cache.GetSkinningQuery(p)
  if sq and sq.HasJointInfluences():
   assert not sq.HasBlendShapes(),'Explicit blend shape evaluation required'
   assert sq.ComputeSkinnedPoints(skintrans,points,Usd.TimeCode(0));matrix=UsdGeom.Xformable(skeleton).ComputeLocalToWorldTransform(Usd.TimeCode(0));method='UsdSkel.ComputeSkinnedPoints'
  else:matrix=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode(0));method='static vertices'
  pts=np.array([matrix.Transform(Gf.Vec3d(*v)) for v in points]);arrays[p.GetName()]=pts
  records.append(dict(path=str(p.GetPath()),method=method,points=len(pts),bounds=[pts.min(0).tolist(),pts.max(0).tolist()]))
 allp=np.concatenate(list(arrays.values()));jworld=query.ComputeJointWorldTransforms(UsdGeom.XformCache(Usd.TimeCode(0)))
 evidence=dict(source=source,pose_changes=changes,meshes=records,height=float(np.ptp(allp[:,2])),bounds=[allp.min(0).tolist(),allp.max(0).tolist()],joints={j:list(m.ExtractTranslation()) for j,m in zip(joints,jworld) if any(j.endswith('/'+x) for x in ['Head','L_Eye','R_Eye','L_Hand','R_Hand','L_Foot','R_Foot','L_Upperarm','R_Upperarm','L_Forearm','R_Forearm'])})
 skin=arrays['trans__organic__malecaucasianskin'];slices=[]
 for z in [1.65,1.68,1.70,1.72,1.74,1.76]:
  pts=skin[(abs(skin[:,2]-z)<.008)]
  slices.append(dict(z=z,n=len(pts),bounds=[pts.min(0).tolist(),pts.max(0).tolist()] if len(pts) else None))
 evidence['head_slices']=slices;stage.GetRootLayer().Save();(ROOT/'reports/step2_1/character_geometry.json').write_text(json.dumps(evidence,indent=2));cachepath=ROOT/'.cache/step2_1';cachepath.mkdir(parents=True,exist_ok=True);np.savez_compressed(cachepath/'posed_vertices.npz',**arrays)
 print('CHARACTER',json.dumps(evidence),flush=True)
 office=Usd.Stage.Open(data['assets']['office']['url']);ceilings=[]
 for p in office.TraverseAll():
  if 'SM_Ceiling' in str(p.GetPath()) and p.GetPath().pathElementCount<4:
   ceilings.append(dict(path=str(p.GetPath()),active=p.IsActive(),instance=p.IsInstance(),visibility=str(UsdGeom.Imageable(p).GetVisibilityAttr().Get()),references=str(p.GetMetadata('references')),payload=str(p.GetMetadata('payload'))))
 (ROOT/'reports/step2_1/ceiling_inspection.json').write_text(json.dumps(ceilings,indent=2));print('CEILINGS',ceilings[:3],len(ceilings),flush=True)
except Exception as e:
 traceback.print_exc();(ROOT/'reports/step2_1/geometry_error.json').write_text(json.dumps({'error':str(e),'traceback':traceback.format_exc()}));raise
finally:app.close()
