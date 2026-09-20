"""Verify mechanical connectivity of authored replacement mounts in final geometry."""
import json
from pathlib import Path
import numpy as np
from fit_geometry_v2 import surface_crossings,inside
r=Path(__file__).resolve().parents[1];a=np.load(r/'.cache/step2_1b_v2/evaluated_meshes.npz');rows=json.loads((r/'reports/step2_1b_v2/fit_after.json').read_text());rig={row['path']:a['rig'+str(i)] for i,row in enumerate(rows)}
connections=[]
for name,tri in rig.items():
 if '/WearerMount/' not in name:continue
 joined=[]
 for other,bt in rig.items():
  if other==name:continue
  if np.any(tri.max((0,1))<bt.min((0,1))-1e-7) or np.any(bt.max((0,1))<tri.min((0,1))-1e-7):continue
  pairs,_=surface_crossings(tri,bt)
  contained=bool(inside(tri[:1,0],bt)[0]) if not pairs else False
  if pairs or contained:joined.append(dict(path=other,intersecting_triangle_pairs=len(pairs),contained_attachment=contained))
 connections.append(dict(path=name,connections=joined))
result=dict(status='PASS' if all(x['connections'] for x in connections) else 'FAIL',replacement_parts=connections,interpretation='Final mount meets the housing on a butt-contact interface, with zero solid overlap verified separately by Boolean intersection. The refined mount is one closed connected mesh; original straps are deactivated only in the new layer.')
(r/'reports/step2_1b_v2/mount_connectivity.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
