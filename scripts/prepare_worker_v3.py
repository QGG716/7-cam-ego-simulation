"""Generate a new bareheaded scene and a fresh head-fitted initial mount."""
import sys,json,traceback,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
RPT=ROOT/'reports/step2_1b_v3';SC=ROOT/'scenes/step2_1b_v3';CF=ROOT/'config/step2_1b_v3';CACHE=ROOT/'.cache/step2_1b_v3'
for d in [RPT,SC,CF,CACHE]:d.mkdir(parents=True,exist_ok=True)
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'sync_loads':False})
try:
 import numpy as np
 from pxr import Usd,UsdGeom,Gf,Vt
 from scipy.spatial import ConvexHull
 from mesh_scene_v3 import extract
 from fit_geometry_v2 import audit
 p=json.loads((ROOT/'config/step2_1b_v2/final_placement.json').read_text());R=np.array(p['R_world_B']);t=np.array(p['rig_translation_world_m'])
 path=SC/'indoor_worker.usda';path.write_text('#usda 1.0\n(defaultPrim="World"\nmetersPerUnit=1\nupAxis="Z"\nsubLayers=[@../step2_1b_v2/indoor_worker.usda@])\n')
 stage=Usd.Stage.Open(str(path));hat=[prim for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/Person')) if prim.IsA(UsdGeom.Mesh) and 'hardhat' in prim.GetName().lower()];assert len(hat)==1
 removed=[str(prim.GetPath()) for prim in hat]
 for prim in hat:prim.SetActive(False)
 body,vertices=extract(stage,'/World/Person');assert len(body)==8 and not any('hardhat' in s for s in body)
 pts=np.concatenate(list(vertices.values()));skin=np.concatenate([v for name,v in vertices.items() if 'skin' in name.lower()]);height=float(skin[:,2].max()-pts[:,2].min());assert abs(height-1.8)<1e-7
 p['worker'].update(final_height_m=height,overall_person_with_attachments_height_m=float(np.ptp(pts[:,2])),helmet_removed=True,removed_prims=removed,geometry_change_from_v2='Only hardhat mesh deactivated; all other skinned geometry and scale/pose unchanged',meshes=[dict(path=name,vertices=len(vertices[name]),triangles=len(tri)) for name,tri in body.items()])
 objects,_=extract(stage,'/World/Rig');before=audit(objects,body);(RPT/'fit_before.json').write_text(json.dumps(before,indent=2))
 fixed={name:tri for name,tri in objects.items() if '/WearerMount/' not in name};assert not any(row.get('triangle_crossings',0) or row.get('human_vertices_inside_solid',0) for row in before if '/WearerMount/' not in row['path'])
 triangles=np.concatenate(list(body.values()));zlo=t[2]-.008;zhi=t[2]+.008;bandtri=triangles[(triangles.max(1)[:,2]>=zlo)&(triangles.min(1)[:,2]<=zhi)];xy=((bandtri.reshape(-1,3)-t)@R)[:,:2];poly=xy[ConvexHull(xy).vertices]
 def offset(poly,dist):
  edges=np.roll(poly,-1,axis=0)-poly;n=np.column_stack((edges[:,1],-edges[:,0]));n/=np.linalg.norm(n,axis=1)[:,None];b=np.einsum('ij,ij->i',n,poly)+dist
  return np.array([np.linalg.solve(np.stack([n[i-1],n[i]]),[b[i-1],b[i]]) for i in range(len(poly))])
 inner=offset(poly,.001);outer=offset(poly,.006);n=len(inner);v=np.vstack([np.column_stack((a,np.full(n,z))) for z in [-.008,.008] for a in [inner,outer]]);faces=[]
 for i in range(n):
  j=(i+1)%n;faces.extend([[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],[i,2*n+i,2*n+j,j],[n+i,n+j,3*n+j,3*n+i]])
 def mesh(name,v,faces):
  prim=stage.OverridePrim(name);prim.SetActive(True);m=UsdGeom.Mesh(prim);m.GetPointsAttr().Set(Vt.Vec3fArray(v.tolist()));m.GetFaceVertexCountsAttr().Set([len(f) for f in faces]);m.GetFaceVertexIndicesAttr().Set(np.array(faces).reshape(-1).tolist());m.CreateExtentAttr().Set([Gf.Vec3f(*v.min(0)),Gf.Vec3f(*v.max(0))])
 mesh('/World/Rig/WearerMount/FittedBand',v,faces)
 front=float(outer[:,0].max());lo=[front-.002,-.012,-.007];hi=[-.030,.012,.007];v=np.array([[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]]);faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];mesh('/World/Rig/WearerMount/ForeheadBridge',v,faces)
 p.update(rig_translation_before_m=t.tolist(),translation_delta_world_m=[0,0,0],rotation_delta_deg=[0,0,0],translation_reason='No additional rigid adjustment needed after helmet removal; freshly checked fixed hardware',fit_status='PENDING_FINAL_REFINEMENT')
 p['mount']=dict(replacement='new bare-head convex fitted band and forehead bridge before clearance refinement',band_inner_B_xy_m=inner.tolist(),band_outer_B_xy_m=outer.tolist(),band_height_m=.016,thickness_m=.005,nominal_min_clearance_m=.001)
 stage.GetRootLayer().Save();objects,_=extract(stage,'/World/Rig');after=audit(objects,body);p['fit_status']='PASS' if not any(r.get('triangle_crossings',0) or r.get('human_vertices_inside_solid',0) for r in after) else 'FAIL'
 (CF/'final_placement.json').write_text(json.dumps(p,indent=2));(RPT/'fit_after.json').write_text(json.dumps(after,indent=2));np.savez_compressed(CACHE/'evaluated_meshes.npz',**{'body'+str(i):v for i,v in enumerate(body.values())},**{'rig'+str(i):v for i,v in enumerate(objects.values())})
 (RPT/'worker_measurement.json').write_text(json.dumps(p['worker'],indent=2));print('BAREHEAD_PREPARED',height,p['fit_status'],flush=True)
except Exception as e:
 (RPT/'prepare_error.json').write_text(json.dumps(dict(error=str(e),traceback=traceback.format_exc()),indent=2));raise
finally:app.close()
