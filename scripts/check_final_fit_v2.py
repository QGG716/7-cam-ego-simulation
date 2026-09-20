"""Independent final triangle and closed-surface containment audit from evaluated cache."""
import json
from pathlib import Path
import numpy as np
from fit_geometry_v2 import surface_crossings,inside
ROOT=Path(__file__).resolve().parents[1];r=ROOT/'reports/step2_1b_v2'
a=np.load(ROOT/'.cache/step2_1b_v2/evaluated_meshes.npz');body={k:a[k] for k in a.files if k.startswith('body')};rig={k:a[k] for k in a.files if k.startswith('rig')}
def topology(tri):
 pts,inv=np.unique(np.round(tri.reshape(-1,3),8),axis=0,return_inverse=True);idx=inv.reshape(-1,3);edges=np.concatenate([idx[:,[0,1]],idx[:,[1,2]],idx[:,[2,0]]]);edges.sort(axis=1);_,counts=np.unique(edges,axis=0,return_counts=True)
 parent=np.arange(len(pts))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for u,v in edges:
  u=find(u);v=find(v)
  if u!=v:parent[u]=v
 components={}
 for i in range(len(pts)):components.setdefault(find(i),pts[i])
 return bool(np.all(counts==2)),np.array(list(components.values())),dict(vertices=len(pts),components=len(components),non_two_manifold_edges=int((counts!=2).sum()))
closed={};bodytop={}
for k,tri in body.items():
 watertight,_,info=topology(tri);bodytop[k]=dict(watertight=watertight,**info)
 if watertight:closed[k]=tri
rows=[]
for k,tri in rig.items():
 hits={};contained={};_,representatives,_=topology(tri)
 for name,bt in body.items():
  pairs,co=surface_crossings(tri,bt)
  if pairs:hits[name]=len(pairs)
 for name,bt in closed.items():
  count=int(inside(representatives,bt).sum())
  if count:contained[name]=count
 rows.append(dict(mesh=k,triangle_crossings=hits,rig_components_inside_closed_person_mesh=contained))
result=dict(status='PASS' if not any(x['triangle_crossings'] or x['rig_components_inside_closed_person_mesh'] for x in rows) else 'FAIL',surface_tests='all final rig triangles against every final body, garment and helmet triangle; segment-triangle tests both directions, coplanar SAT',coordinate_tolerance_m=1e-8,relative_parallel_tolerance=1e-12,contact_reporting_tolerance_m=.0001,body_topology=bodytop,rows=rows,limitations='Open garment/skin meshes have no unique solid interior. Containment is asserted only for closed meshes, with surface tests for all meshes; no pressure, comfort or mechanics conclusion.')
(r/'independent_fit_check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
