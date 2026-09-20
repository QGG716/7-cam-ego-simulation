"""Cut actual clearance channels into new mounts; frozen hardware is never changed."""
import json,sys
from pathlib import Path
import numpy as np
import manifold3d as md
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,geometry_specs
p=json.loads((ROOT/'config/step2_1b_v3/final_placement.json').read_text());R=np.array(p['R_world_B']);t=np.array(p['rig_translation_world_m']);a=np.load(ROOT/'.cache/step2_1b_v3/evaluated_meshes.npz');rows=json.loads((ROOT/'reports/step2_1b_v3/fit_after.json').read_text());objects={row['path']:(a['rig'+str(i)]-t)@R*1000 for i,row in enumerate(rows)}
# Reconstruct the initial mount from saved fit parameters, so this also works after
# the final cache has replaced the two initial mounting meshes with one solid.
inner=np.array(p['mount']['band_inner_B_xy_m']);outer=np.array(p['mount']['band_outer_B_xy_m']);n=len(inner)
v=np.vstack([np.column_stack((a,np.full(n,z))) for z in [-.008,.008] for a in [inner,outer]]).astype(np.float32).astype(float)*1000;faces=[]
for i in range(n):
 j=(i+1)%n;faces.extend([[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],[i,2*n+i,2*n+j,j],[n+i,n+j,3*n+j,3*n+i]])
tri=np.array([[f[0],f[k],f[k+1]] for f in faces for k in [1,2]]);objects['/World/Rig/WearerMount/FittedBand']=v[tri]
front=float(outer[:,0].max());lo=[front-.002,-.012,-.007];hi=[-.030,.012,.007];v=np.array([[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]],np.float32).astype(float)*1000;faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];tri=np.array([[f[0],f[k],f[k+1]] for f in faces for k in [1,2]]);objects['/World/Rig/WearerMount/ForeheadBridge']=v[tri]

def solid(tris):
 points,inv=np.unique(np.round(tris.reshape(-1,3),6),axis=0,return_inverse=True);tri=inv.reshape(-1,3)
 volume=np.einsum('ij,ij->i',points[tri[:,0]],np.cross(points[tri[:,1]],points[tri[:,2]])).sum()/6
 if volume<0:tri=tri[:,[0,2,1]]
 result=md.Manifold(md.Mesh(points.astype(np.float32),tri.astype(np.uint32)));assert str(result.status())=='Error.NoError',result.status();return result
mount=solid(objects['/World/Rig/WearerMount/FittedBand'])+solid(objects['/World/Rig/WearerMount/ForeheadBridge']);before=mount.volume();cuts=[]
for g in geometry_specs(load_config()):
 if g['group']=='Housing':
  cutter=solid(objects['/World/Rig/Housing/'+g['name']]);gap=0.
 elif g['name']=='right_heatsink':
  gap=.5;cutter=md.Manifold.cube(np.array(g['size_mm'])+2*gap,True).translate(g['center_mm'])
 elif g['name'].startswith('usb_cable_'):
  gap=.5;o=np.array(g['a_mm'],float);end=np.array(g['b_mm'],float);z=end-o;length=np.linalg.norm(z);z/=length;x=np.cross(z,[0,0,1]);x/=np.linalg.norm(x);y=np.cross(z,x)
  cutter=md.Manifold.cylinder(length+2*gap,g['radius_mm']+gap,circular_segments=128).transform(np.column_stack((x,y,z,o-z*gap)))
 else:continue
 intersection=mount^cutter;removed=intersection.volume();mount=mount-cutter
 if removed>1e-6:cuts.append(dict(part=g['name'],clearance_mm=gap,removed_volume_mm3=removed))
assert str(mount.status())=='Error.NoError';components=mount.decompose();assert len(components)==1,('Disconnected mount',len(components))
residual={name:float((mount ^ solid(tri)).volume()) for name,tri in objects.items() if '/WearerMount/' not in name};assert max(residual.values())<.01,residual
if '--verify' not in sys.argv:(ROOT/'reports/step2_1b_v3/mount_hardware_boolean.json').write_text(json.dumps(dict(status='PASS',intersection_volume_mm3=residual,numerical_volume_tolerance_mm3=.01,method='Closed oriented triangle solids, Manifold3D Boolean intersection; housing butt-contact allowed; 0.5 mm cutter enlargement for cable and heatsink',connected_components=len(components)),indent=2))
m=mount.to_mesh();vertices=np.asarray(m.vert_properties)[:,:3]/1000;triangles=np.asarray(m.tri_verts)
result=dict(vertices_B_m=vertices.tolist(),triangles=triangles.tolist(),method='Manifold3D union of replacement band/bridge, subtraction of fixed housing at butt-contact and 0.5 mm clearance around fixed heatsink/cable; hardware untouched',library='manifold3d 3.5.3',connected_components=len(components),closed_manifold=True,cuts=cuts,volume_before_mm3=before,volume_after_mm3=mount.volume())
if '--verify' not in sys.argv:(ROOT/'config/step2_1b_v3/refined_mount.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['vertices_B_m','triangles']},indent=2));print('vertices',len(vertices),'triangles',len(triangles))
