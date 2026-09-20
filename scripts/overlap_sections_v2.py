"""Projection-based physical section overlap; no screen-space polygon intersections."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs
from projection import project,unproject
COLORS={'C0':'#1478AE','C1':'#21A78F','C2':'#D6AB45','C3':'#3969AD','C5':'#58B4C6','C4':'#A65252','C6':'#CB9167','two':'#F07824','three':'#8935A7','occlusion':'#6E7680'}
def boundary_uv(c,n=192):
 o=c['optics'];a=np.linspace(0,2*np.pi,n,endpoint=False);co=np.cos(a);si=np.sin(a)
 rad=np.minimum(np.divide(o['resolution'][0]/2,abs(co),out=np.full(n,np.inf),where=abs(co)>1e-12),np.divide(o['resolution'][1]/2,abs(si),out=np.full(n,np.inf),where=abs(si)>1e-12))
 if o['valid_radius_px'] is not None:rad=np.minimum(rad,o['valid_radius_px'])
 return np.column_stack((co*rad+o['cx_px'],si*rad+o['cy_px']))
def run():
 out=ROOT/'outputs/step2_1b_v2/debug';out.mkdir(parents=True,exist_ok=True);conf=ROOT/'config/step2_1b_v2'
 p=json.loads((conf/'final_placement.json').read_text());R=np.array(p['R_world_B']);t=np.array(p['rig_translation_world_m']);specs={c['id']:c for c in camera_specs(load_config())}
 groups={'B':dict(ids=['C0','C1','C2'],fixed_B_X_m=.25,u_B_Y_m=[-1.5,1.5],v_B_Z_m=[-.75,.75],shape=[751,1501]),'C':dict(ids=['C3','C5'],fixed_B_X_m=-.016,u_B_Y_m=[-.45,.45],v_B_Z_m=[-.45,.45],shape=[901,901]),'D':dict(ids=['C4','C6'],fixed_B_X_m=-.016,u_B_Y_m=[-.45,.45],v_B_Z_m=[-.45,.45],shape=[901,901])}
 checks={}
 for cid,c in specs.items():
  uv=boundary_uv(c);rays=unproject(c,uv);uv2,_=project(c,rays);err=float(np.max(abs(uv2-uv)));theta=np.rad2deg(np.arccos(np.clip(rays[:,2],-1,1)));assert err<1e-8
  if cid in ['C3','C4','C5','C6']:assert np.allclose(theta,110) and np.all(rays[:,2]<0)
  checks[cid]=dict(roundtrip_max_px=err,boundary_samples=len(uv),maximum_offaxis_deg=float(theta.max()),backward_hemisphere_samples=int((rays[:,2]<0).sum()))
 counts={}
 for name,g in groups.items():
  ny,nx=g['shape'];u=np.linspace(*g['u_B_Y_m'],nx);v=np.linspace(*g['v_B_Z_m'],ny);U,V=np.meshgrid(u,v);b=np.stack((np.full(U.shape,g['fixed_B_X_m']),U,V),axis=-1);world=b@R.T+t;valid=[]
  for cid in g['ids']:
   c=specs[cid];origin=t+R@np.array(c['position_mm'])/1000;rw=R@np.array(c['R_B_optical']);_,mask=project(c,(world-origin)@rw);valid.append(mask)
   # Independent B-space formulation must classify exactly the same world points.
   _,bmask=project(c,(b-np.array(c['position_mm'])/1000)@np.array(c['R_B_optical']));assert np.array_equal(mask,bmask)
  stack=np.array(valid);total=stack.sum(0);labels=np.zeros(U.shape,np.uint8)
  for i,mask in enumerate(valid):labels[mask & (total==1)]=i+1
  labels[total==2]=4;labels[total==3]=5
  np.savez_compressed(out/('section_'+name+'.npz'),labels=labels,u=u,v=v,membership_bits=sum(mask.astype(np.uint8)*(1<<i) for i,mask in enumerate(valid)))
  categories={str(i+1):'only_'+cid for i,cid in enumerate(g['ids'])};categories.update({'0':'outside_group','4':'exactly_two','5':'all_three'})
  counts[name]={categories[str(k)]:int((labels==k).sum()) for k in map(int,categories)};g.update(categories=categories,world_plane_origin_m=(t+R@np.array([g['fixed_B_X_m'],0,0])).tolist(),world_u_direction=R[:,1].tolist(),world_v_direction=R[:,2].tolist(),world_normal=R[:,0].tolist(),grid_spacing_m=[float(u[1]-u[0]),float(v[1]-v[0])],section_only=True,finite_range_clipping=False)
 config=dict(groups=groups,colors=COLORS,envelope_display_radius_m=.40,section_interpretation='Unoccluded ideal geometric membership at identical world points on one physical plane per group; no range truncation in section, display window only; not full 3D volume or seven-camera union coverage',config_sha256=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest())
 (conf/'figure_config.json').write_text(json.dumps(config,indent=2));(ROOT/'reports/step2_1b_v2/overlap_checks.json').write_text(json.dumps(dict(status='PASS',boundary_checks=checks,section_category_sample_counts=counts,world_vs_body_classification='identical',zero_categories_are_not_fabricated=True),indent=2));print(json.dumps(counts,indent=2))
if __name__=='__main__':run()
