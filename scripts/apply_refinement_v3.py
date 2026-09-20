"""Apply authorized industrial colors and the continuous clearance-cut mount overlay."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'sync_loads':False})
try:
 import numpy as np
 from pxr import Usd,UsdGeom,UsdShade,Sdf,Gf,Vt
 from fit_geometry_v2 import audit
 stage=Usd.Stage.Open(str(ROOT/'scenes/step2_1b_v3/indoor_worker.usda'))
 palette={'vest':(.95,.31,.025),'workpants':(.025,.065,.12),'tshirt':(.08,.14,.22),'boots':(.035,.035,.04),'gloves':(.30,.32,.34),'hardhat':(1.,.69,.025),'reflective':(.74,.77,.8)};materials={}
 for name,color in palette.items():
  path='/World/WorkerAppearance/'+name;mat=UsdShade.Material.Define(stage,path);shader=UsdShade.Shader.Define(stage,path+'/Surface');shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.65);mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');materials[name]=mat
 for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/Person')):
  if not prim.IsA(UsdGeom.Mesh):continue
  name=prim.GetName().lower();key='reflective' if 'reflective' in name else next((k for k in palette if k in name),None)
  if key:UsdShade.MaterialBindingAPI.Apply(prim).Bind(materials[key],bindingStrength=UsdShade.Tokens.strongerThanDescendants)
 cfg=json.loads((ROOT/'config/step2_1b_v3/refined_mount.json').read_text());mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Rig/WearerMount/FittedBand'));vertices=np.array(cfg['vertices_B_m']);indices=np.array(cfg['triangles']);mesh.GetPointsAttr().Set(Vt.Vec3fArray(vertices.tolist()));mesh.GetFaceVertexCountsAttr().Set([3]*len(indices));mesh.GetFaceVertexIndicesAttr().Set(indices.reshape(-1).tolist());mesh.CreateExtentAttr().Set([Gf.Vec3f(*vertices.min(0)),Gf.Vec3f(*vertices.max(0))]);stage.GetPrimAtPath('/World/Rig/WearerMount/ForeheadBridge').SetActive(False);stage.GetRootLayer().Save()
 path=ROOT/'config/step2_1b_v3/final_placement.json';p=json.loads(path.read_text());p['worker']['appearance']=dict(method='Official construction worker geometry retained; user-authorized industrial palette on apparel/PPE; original skin material retained; source asset read-only',palette=palette)
 p['mount']['refinement']={k:v for k,v in cfg.items() if k not in ['vertices_B_m','triangles']};p['mount']['replacement']='one closed connected fitted band with integrated forehead mount and explicit clearance channels'
 cachepath=ROOT/'.cache/step2_1b_v3/evaluated_meshes.npz';a=np.load(cachepath);data={k:a[k] for k in a.files if k!='rig14'};m=np.array(UsdGeom.Xformable(mesh).ComputeLocalToWorldTransform(0));actual=np.array(mesh.GetPointsAttr().Get())@m[:3,:3]+m[3,:3];data['rig13']=actual[indices];np.savez_compressed(cachepath,**data)
 body={k:v for k,v in data.items() if k.startswith('body')};rows=json.loads((ROOT/'reports/step2_1b_v3/fit_after.json').read_text());rows=[r for r in rows if '/WearerMount/' not in r['path']]+audit({'/World/Rig/WearerMount/FittedBand':data['rig13']},body);(ROOT/'reports/step2_1b_v3/fit_after.json').write_text(json.dumps(rows,indent=2));p['fit_status']='PASS' if not any(r.get('triangle_crossings',0) or r.get('human_vertices_inside_solid',0) for r in rows) else 'FAIL';path.write_text(json.dumps(p,indent=2));print('REFINEMENT_APPLIED',p['fit_status'],flush=True)
except Exception as e:
 import traceback
 (ROOT/'reports/step2_1b_v3/refinement_error.json').write_text(json.dumps(dict(error=str(e),traceback=traceback.format_exc()),indent=2));raise
finally:app.close()
