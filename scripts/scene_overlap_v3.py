"""Reproject measured scene points into each actual camera; soft illustrative overlap."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from projection import project,unproject
from rig_common import camera_specs,load_config
from overlap_sections_v2 import COLORS,boundary_uv
DEBUG=ROOT/'outputs/step2_1b_v3/debug';RPT=ROOT/'reports/step2_1b_v3';CONF=ROOT/'config/step2_1b_v3'
GROUPS={'B':dict(reference='C0',ids=['C0','C1','C2']),'C':dict(reference='UP_REF',ids=['C3','C5']),'D':dict(reference='DOWN_REF',ids=['C4','C6'])}
SOFT={'two':'#6B8198','three':'#927DA4','unconfirmed':'#9DA1A5'}
def color(hex):return np.array([int(hex[i:i+2],16) for i in [1,3,5]],float)
def run():
 depth_checks=json.loads((DEBUG/'depth_validation.json').read_text())
 assert sum(r['samples'] for r in depth_checks)>100 and not any(r['errors_over_5mm'] for r in depth_checks),'Native radial-depth validation failed'
 records={r['camera_id']:r for r in json.loads((DEBUG/'sensor_view_checks.json').read_text())};specs={c['id']:c for c in camera_specs(load_config())};checks={};categories={}
 for cid,c in specs.items():
  uv=boundary_uv(c);rr=unproject(c,uv);err=float(np.max(abs(project(c,rr)[0]-uv)));assert err<1e-8
  if cid in ['C3','C4','C5','C6']:assert np.allclose(np.rad2deg(np.arccos(rr[:,2])),110)
  checks[cid]=dict(boundary_roundtrip_px=err,max_offaxis_deg=float(np.rad2deg(np.arccos(rr[:,2])).max()))
 for name,g in GROUPS.items():
  ref=records[g['reference']];refcam=dict(optics=ref['optics']);w,h=ref['resolution'];data=np.load(DEBUG/(g['reference']+'_depth.npz'));depth=data['distance_m'];valid=data['valid'];rr=unproject(refcam,np.stack(np.meshgrid(np.arange(w)+.5,np.arange(h)+.5),axis=-1));finite=valid&np.isfinite(depth)&(depth>.0001)&(depth<100)
  safe=np.where(finite,depth,1.);world=np.array(ref['position_world_m'])+(rr@np.array(ref['R_world_optical']).T)*safe[...,None];members=[];geo=[]
  for cid in g['ids']:
   c=specs[cid];record=records[cid];d=world-np.array(record['position_world_m']);uv,inside=project(c,d@np.array(record['R_world_optical']));distance=np.linalg.norm(d,axis=-1);geo.append(inside&finite)
   target=np.load(DEBUG/(cid+'_depth.npz'));td=target['distance_m'];tv=target['valid'];tw,th=c['optics']['resolution'];u=np.floor(uv[...,0]).astype(int);v=np.floor(uv[...,1]).astype(int);best=np.full((h,w),np.inf)
   # Closest depth residual in a 3x3 neighborhood mitigates raster edges;
   # this is an explicit approximate visibility test, not a stereo-match metric.
   for dv in [-1,0,1]:
    for du in [-1,0,1]:
     uu=np.clip(u+du,0,tw-1);vv=np.clip(v+dv,0,th-1);sample=td[vv,uu];ok=tv[vv,uu]&np.isfinite(sample)&(u+du>=0)&(u+du<tw)&(v+dv>=0)&(v+dv<th)
     best=np.minimum(best,np.where(ok,abs(sample-distance),np.inf))
   confirmed=inside&finite&(best<=.025+.005*distance)
   if cid==g['reference']:assert np.all(confirmed[finite]),'Reference depth roundtrip inconsistency'
   members.append(confirmed)
  masks=np.array(members);count=masks.sum(0).astype(np.uint8);labels=np.zeros((h,w),np.uint8)
  for i,mask in enumerate(members):labels[mask&(count==1)]=i+1
  labels[count==2]=4;labels[count==3]=5;labels[~finite]=255
  raw=np.asarray(Image.open(DEBUG/(g['reference']+'_scene.png')).convert('RGB'));result=raw.astype(float)
  for i,cid in enumerate(g['ids']):
   mask=labels==i+1;result[mask]=.96*raw[mask]+.04*color(COLORS[cid])
  for label,key,alpha in [(4,'two',.14),(5,'three',.18),(0,'unconfirmed',.08)]:
   mask=labels==label;result[mask]=(1-alpha)*raw[mask]+alpha*color(SOFT[key])
  result[~valid]=raw[~valid];Image.fromarray(np.round(result).clip(0,255).astype(np.uint8)).save(DEBUG/('view_'+name+'_overlap.png'))
  np.savez_compressed(DEBUG/('view_'+name+'_overlap.npz'),labels=labels,member_bits=sum(m.astype(np.uint8)*(1<<i) for i,m in enumerate(members)),geometry_count=np.array(geo).sum(0).astype(np.uint8),finite_reference=finite)
  categories[name]=dict(reference=g['reference'],category_pixels={**{'only_'+cid:int((labels==i+1).sum()) for i,cid in enumerate(g['ids'])},'two':int((labels==4).sum()),'three':int((labels==5).sum()),'unconfirmed':int((labels==0).sum()),'invalid_or_no_depth':int((labels==255).sum())},mean_absolute_RGB_change=float(np.abs(result-raw).mean()),method='same reference scene point, actual per-camera origin/extrinsics/project(), 3x3 nearest radial-depth residual <= 25 mm + 0.5% distance')
 config=dict(groups=GROUPS,colors=COLORS,overlap_colors=SOFT,alpha=dict(single=.04,two=.14,three=.18,unconfirmed=.08),envelope_display_radius_m=.4,depth_tolerance_m=.025,depth_relative_tolerance=.005,depth_neighborhood=3,limits='Illustrative approximate scene visibility overlap, not exact occlusion boundary, stereo matching or union coverage. Pixels without finite reference depth are not classified. Actual C0 frame cannot display C1/C2-only directions outside its image. UP/DOWN midpoint views are additional reference cameras, not moved sensors.',config_sha256=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest())
 (CONF/'figure_config.json').write_text(json.dumps(config,indent=2));(RPT/'overlap_checks.json').write_text(json.dumps(dict(status='PASS',boundary_checks=checks,groups=categories),indent=2));print(json.dumps(categories,indent=2))
if __name__=='__main__':run()
