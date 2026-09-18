"""Inspect only the requested NVIDIA assets in the installed Isaac environment."""
import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/step2_1';OUT.mkdir(parents=True,exist_ok=True)
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','multi_gpu':False})
try:
 import omni.client,carb
 from isaacsim.storage.native import get_assets_root_path
 from pxr import Usd,UsdGeom,UsdSkel
 root=get_assets_root_path();print('ASSET_ROOT',root,flush=True)
 paths={'office':root+'/Isaac/Environments/Office/office.usd','doctor':root+'/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd'}
 result=json.loads((OUT/'asset_probe.json').read_text()) if (OUT/'asset_probe.json').exists() else {'asset_root':root,'assets':{}}
 for name,url in paths.items():
  if name in result['assets']:continue
  status,entry=omni.client.stat(url);print('STAT',name,url,status,flush=True)
  if status!=omni.client.Result.OK:
   parent=url.rsplit('/',2)[0];ls,entries=omni.client.list(parent);print('PARENT',parent,ls,[x.relative_path for x in entries],flush=True);continue
  stage=Usd.Stage.Open(url);print('OPEN',name,bool(stage),flush=True)
  record={'url':url,'upAxis':str(UsdGeom.GetStageUpAxis(stage)),'metersPerUnit':UsdGeom.GetStageMetersPerUnit(stage),'defaultPrim':str(stage.GetDefaultPrim().GetPath()),'start':stage.GetStartTimeCode(),'end':stage.GetEndTimeCode(),'prims':[]}
  bc=UsdGeom.BBoxCache(Usd.TimeCode(0),[UsdGeom.Tokens.default_,UsdGeom.Tokens.render],useExtentsHint=False)
  for p in stage.Traverse():
   if p.IsA(UsdGeom.Mesh) or p.IsA(UsdSkel.Skeleton) or p.IsA(UsdSkel.Animation) or 'ceiling' in str(p.GetPath()).lower() or 'roof' in str(p.GetPath()).lower():
    row={'path':str(p.GetPath()),'type':p.GetTypeName()}
    if p.IsA(UsdGeom.Mesh):
     mesh=UsdGeom.Mesh(p);row.update(vertices=len(mesh.GetPointsAttr().Get() or []),visibility=str(UsdGeom.Imageable(p).ComputeVisibility()),bounds=[list(bc.ComputeWorldBound(p).ComputeAlignedRange().GetMin()),list(bc.ComputeWorldBound(p).ComputeAlignedRange().GetMax())])
    if p.IsA(UsdSkel.Skeleton):row.update(joints=list(UsdSkel.Skeleton(p).GetJointsAttr().Get()),animations=[str(x) for x in UsdSkel.BindingAPI(p).GetAnimationSourceRel().GetTargets()])
    if p.IsA(UsdSkel.Animation):row.update(joints=list(UsdSkel.Animation(p).GetJointsAttr().Get()),rotation_times=UsdSkel.Animation(p).GetRotationsAttr().GetTimeSamples())
    record['prims'].append(row)
  result['assets'][name]=record;(OUT/'asset_probe.json').write_text(json.dumps(result,indent=2));print('INSPECTED',name,len(record['prims']),flush=True)
except Exception as e:
 traceback.print_exc();(OUT/'asset_probe_error.json').write_text(json.dumps({'error':str(e),'traceback':traceback.format_exc()}));raise
finally:app.close()
