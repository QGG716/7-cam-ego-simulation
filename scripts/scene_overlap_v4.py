"""Per-actual-camera scene-point overlap with a single documented display transform."""
import json,sys,hashlib,shutil
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import camera_specs,load_config
from projection import project,unproject
SOURCE=ROOT/'outputs/step2_1b_v3/debug';OUT=ROOT/'outputs/step2_1b_v4';RPT=ROOT/'reports/step2_1b_v4';CONF=ROOT/'config/step2_1b_v4'
GROUPS={'B':['C1','C0','C2'],'C':['C3','C5'],'D':['C4','C6']}
COLORS={2:'#7396AB',3:'#A18BAF'}
EXPOSURE_EV=1.5

def display_rgb(raw):
 s=raw.astype(float)/255;linear=np.where(s<=.04045,s/12.92,((s+.055)/1.055)**2.4);linear=np.clip(linear*2**EXPOSURE_EV,0,1)
 return np.round(255*np.where(linear<=.0031308,12.92*linear,1.055*linear**(1/2.4)-.055)).astype(np.uint8)

def run():
 for d in [OUT/'raw',OUT/'display',OUT/'layers',RPT,CONF]:d.mkdir(parents=True,exist_ok=True)
 checks=json.loads((SOURCE/'depth_validation.json').read_text());assert sum(r['samples'] for r in checks)>100 and not any(r['errors_over_5mm'] for r in checks)
 records={r['camera_id']:r for r in json.loads((SOURCE/'sensor_view_checks.json').read_text())};specs={c['id']:c for c in camera_specs(load_config())};results={}
 for group,ids in GROUPS.items():
  for refid in ids:
   ref=records[refid];w,h=ref['resolution'];source=np.load(SOURCE/(refid+'_depth.npz'));depth=source['distance_m'];valid=source['valid'];finite=valid&np.isfinite(depth)&(depth>.0001)&(depth<100)
   rays=unproject(specs[refid],np.stack(np.meshgrid(np.arange(w)+.5,np.arange(h)+.5),axis=-1));world=np.array(ref['position_world_m'])+(rays@np.array(ref['R_world_optical']).T)*np.where(finite,depth,1)[...,None];members=[]
   for cid in ids:
    c=specs[cid];r=records[cid];d=world-np.array(r['position_world_m']);uv,inside=project(c,d@np.array(r['R_world_optical']));distance=np.linalg.norm(d,axis=-1);target=np.load(SOURCE/(cid+'_depth.npz'));td=target['distance_m'];tv=target['valid'];tw,th=c['optics']['resolution'];u=np.floor(uv[...,0]).astype(int);v=np.floor(uv[...,1]).astype(int);best=np.full((h,w),np.inf)
    for dy in [-1,0,1]:
     for dx in [-1,0,1]:
      xx=np.clip(u+dx,0,tw-1);yy=np.clip(v+dy,0,th-1);sample=td[yy,xx];ok=tv[yy,xx]&np.isfinite(sample)&(u+dx>=0)&(u+dx<tw)&(v+dy>=0)&(v+dy<th);best=np.minimum(best,np.where(ok,abs(sample-distance),np.inf))
    confirmed=finite&inside&(best<=.025+.005*distance)
    if cid==refid:assert np.all(confirmed[finite])
    members.append(confirmed)
   count=np.array(members).sum(0).astype(np.uint8);bits=sum(m.astype(np.uint8)*(1<<i) for i,m in enumerate(members));unknown=valid&~finite
   assert np.all(count[finite]>=1)
   shutil.copyfile(SOURCE/(refid+'_scene.png'),OUT/'raw'/(refid+'.png'))
   raw=np.asarray(Image.open(OUT/'raw'/(refid+'.png')).convert('RGB'));base=display_rgb(raw);Image.fromarray(base).save(OUT/'display'/(refid+'.png'))
   layer=np.zeros((h,w,4),np.uint8)
   for n,alpha in [(2,26),(3,31)]:
    col=COLORS[n];rgb=[int(col[k:k+2],16) for k in [1,3,5]];layer[count==n]=[*rgb,alpha]
   yy,xx=np.indices((h,w));hatch=unknown&((xx+yy)%18<2);layer[hatch]=[205,213,219,110]
   # Invalid domain gets a subtle checker only in the explanatory layer.
   checker=np.where(((xx//16+yy//16)%2)==0,22,29).astype(np.uint8)
   for k in range(3):layer[...,k][~valid]=checker[~valid]
   layer[...,3][~valid]=255
   Image.fromarray(layer).save(OUT/'layers'/(refid+'_annotation.png'))
   composite=Image.alpha_composite(Image.fromarray(base).convert('RGBA'),Image.fromarray(layer));composite.convert('RGB').save(OUT/'display'/(refid+'_annotated.png'))
   np.savez_compressed(OUT/'layers'/(refid+'_classification.npz'),count=count,member_bits=bits,valid=valid,unknown=unknown)
   results[refid]=dict(group=group,members=ids,source=(SOURCE/(refid+'_scene.png')).relative_to(ROOT).as_posix(),raw_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),source_file_sha256=hashlib.sha256((SOURCE/(refid+'_scene.png')).read_bytes()).hexdigest(),only_self_pixels=int((count==1).sum()),two_pixels=int((count==2).sum()),three_pixels=int((count==3).sum()),unknown_pixels=int(unknown.sum()),invalid_pixels=int((~valid).sum()),resolution=[w,h])
   print('COMPUTED',refid,flush=True)
 cfg=dict(baseline_commit='1186652946f02437327386856114476a65e5141b',groups=GROUPS,exposure_EV=EXPOSURE_EV,display_transform='sRGB decode -> fixed linear RGB gain 2^1.5 -> clip [0,1] -> sRGB encode; same for all seven images; raw files byte-identical',alpha_two=26/255,alpha_three=31/255,overlap_colors=COLORS,depth_absolute_tolerance_m=.025,depth_relative_tolerance=.005,neighborhood_pixels=3,source_geometry='Unchanged v3 scene, pose, extrinsics, FOV and projection',unknown='Valid image pixel without finite reference depth; sparse gray diagonal hatch; do not equate with occlusion',invalid='Outside actual projection domain; neutral checker in explanation layer only',boundaries='Thin contours of count >= 2 and >= 3 with 3 px Gaussian display-only smoothing; class masks unchanged; valid-domain border separate')
 (CONF/'figure_config.json').write_text(json.dumps(cfg,indent=2)+'\n');(RPT/'image_checks.json').write_text(json.dumps(dict(status='PASS',cameras=results),indent=2)+'\n')
if __name__=='__main__':run()
