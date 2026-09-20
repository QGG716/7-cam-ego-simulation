"""Scoped official worker asset discovery; no library-wide download."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False})
try:
 import omni.client
 from isaacsim.storage.native import get_assets_root_path
 root=get_assets_root_path()+'/Isaac/People/Characters'; result={}
 for name in ['original_male_adult_construction_01','original_male_adult_construction_03','original_male_adult_construction_05']:
  status,entries=omni.client.list(root+'/'+name)
  result[name]={'directory':root+'/'+name,'status':str(status),'files':[e.relative_path for e in entries]}
 from pxr import Usd,UsdGeom,UsdSkel
 for name,row in result.items():
  url=row['directory']+'/'+next(f for f in row['files'] if f.endswith('.usd'))
  stage=Usd.Stage.Open(url);row.update(url=url,upAxis=str(UsdGeom.GetStageUpAxis(stage)),metersPerUnit=UsdGeom.GetStageMetersPerUnit(stage),meshes=[str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)],skeletons=[{'path':str(p.GetPath()),'joints':list(UsdSkel.Skeleton(p).GetJointsAttr().Get())} for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)])
 out=ROOT/'reports/step2_1b_v2';out.mkdir(parents=True,exist_ok=True)
 (out/'worker_discovery.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
finally:app.close()
