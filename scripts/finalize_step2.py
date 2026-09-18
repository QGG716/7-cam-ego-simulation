"""Compare independent RTX labels and analytic hits; generate review images."""
import sys,json,csv,hashlib,colorsys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import binary_dilation,binary_erosion
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from analyze_step2 import OUT,OPTIONS,SHA,components
from rig_common import load_config,camera_specs
fontfile=next((p for p in ['C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if Path(p).exists()),None)
font=ImageFont.truetype(fontfile,20) if fontfile else ImageFont.load_default()
objs=components();colors={o['id']:tuple(int(v*255) for v in colorsys.hsv_to_rgb((o['id']*.61803398875)%1,.68,.96)) for o in objs}
summary=json.loads((OUT/'camera_occlusion_summary.json').read_text());rows=summary['rows'];comparisons=[]
geometry=json.loads((OUT/'geometry_verification.json').read_text())
bounds_checks=[]
for obj,g in zip(objs,geometry['components']):
 assert obj['usd_path']==g['usd_path']
 if obj['kind']=='cylinder':
  aa=np.array(obj['a_mm']);bb=np.array(obj['b_mm']);axis=(bb-aa)/np.linalg.norm(bb-aa);extent=obj['radius_mm']*np.sqrt(np.maximum(0,1-axis**2));lo=np.minimum(aa,bb)-extent;hi=np.maximum(aa,bb)+extent
 else:
  center=np.array(obj['center_mm']);extent=np.array(obj['size_mm'])/2 if obj['kind']=='box' else np.array(obj['radii_mm']);lo=center-extent;hi=center+extent
 error=float(np.max(np.abs(np.array(g['mesh_bounds_B_mm'])-[lo,hi])))
 tolerance=.00001 if obj['kind']=='box' else .1
 assert error<tolerance,(obj['name'],error)
 bounds_checks.append(dict(name=obj['name'],analytic_bounds_B_mm=[lo.tolist(),hi.tolist()],max_bounds_difference_mm=error,engineering_check_tolerance_mm=tolerance))
(OUT/'geometry_bounds_checks.json').write_text(json.dumps(bounds_checks,indent=2))
checks=json.loads((OUT/'label_projection_checks.json').read_text());assert all(r['status']=='PASS' for r in checks),'Labels cannot be declared validated'
for cam in camera_specs(load_config()):
 cid=cam['id'];panels=[]
 for mode in OPTIONS['modes']:
  directory=OUT/mode;analytic=np.load(directory/(cid+'_analytic.npz'));rtx=np.load(directory/(cid+'_rtx.npz'))
  valid=analytic['valid'];a=analytic['blocked'];b=rtx['blocked'];assert np.array_equal(valid,rtx['valid'])
  assert not ((rtx['renderer_instance_id']>1)&(rtx['component_id']==0)&valid).any(),'Unmapped semantic instance'
  assert all(o['group'] in OPTIONS['modes'][mode] for o in objs if ((rtx['component_id']==o['id'])&valid).any())
  if mode=='worn':assert not (np.load(OUT/'body'/(cid+'_rtx.npz'))['blocked']&~b).any()
  meta=json.loads((directory/(cid+'.json')).read_text());assert meta['config_sha256']==SHA and meta['simulation_time_seconds']==0
  rgb=Image.open(directory/(cid+'_raw.png')).convert('RGB');assert rgb.size==tuple(cam['optics']['resolution'])
  edgea=a^binary_erosion(a);edgeb=b^binary_erosion(b);band=binary_dilation(edgea|edgeb,iterations=OPTIONS['boundary_band_px'])&valid
  diff=(a^b)&valid;union=int((a|b).sum());both=a&b
  aid=analytic['first_hit_id'];bid=rtx['component_id'];source_mismatch=(aid!=bid)&both
  entry=dict(camera_id=cid,mode=mode,N_valid=int(valid.sum()),analytic_blocked=int(a.sum()),rtx_blocked=int(b.sum()),area_delta_pixels=int(b.sum())-int(a.sum()),area_delta_pixel_ratio=(int(b.sum())-int(a.sum()))/int(valid.sum()),mask_IoU=int(both.sum())/union if union else None,empty_union=union==0,disagreement_pixels=int(diff.sum()),boundary_band_px=OPTIONS['boundary_band_px'],boundary_band_pixels=int(band.sum()),boundary_disagreement=int((diff&band).sum()),nonboundary_disagreement=int((diff&~band).sum()),first_hit_source_disagreement=int(source_mismatch.sum()),rtx_component_counts={o['name']:int(((bid==o['id'])&valid).sum()) for o in objs},verification='full-resolution RTX labels; projection registration PASS')
  comparisons.append(entry)
  delta=np.zeros((*valid.shape,3),np.uint8);delta[valid]=(24,28,36);delta[a&b]=(80,140,100);delta[a&~b]=(255,60,60);delta[b&~a]=(40,160,255);Image.fromarray(delta).save(directory/(cid+'_rtx_difference.png'))
  color=np.zeros((*valid.shape,3),np.uint8);color[valid]=(225,230,237)
  for oid,col in colors.items():color[aid==oid]=col
  Image.fromarray(color).save(directory/(cid+'_sources_color.png'))
  pic=np.array(rgb);pic[~valid]=0;pic[a]=(pic[a]*.35+color[a]*.65).astype(np.uint8)
  overlay=Image.fromarray(pic);overlay.thumbnail((864,768));legend=Image.new('RGB',(overlay.width+410,max(overlay.height,490)),(20,25,35));legend.paste(overlay,(0,0));draw=ImageDraw.Draw(legend)
  row=next(r for r in rows if r['camera_id']==cid and r['mode']==mode)
  draw.text((overlay.width+14,12),cid+' '+mode+' | analytic first hit',font=font,fill='white');y=52
  for contribution in sorted(row['components'],key=lambda x:-x['N_blocked']):
   if not contribution['N_blocked']:continue
   oid=contribution['component_id'];draw.rectangle((overlay.width+14,y+3,overlay.width+30,y+19),fill=colors[oid]);draw.text((overlay.width+40,y),contribution['name'],font=font,fill='white');y+=25;draw.text((overlay.width+40,y),f'{100*contribution["pixel_ratio"]:.4f}% valid pixels',font=font,fill=(180,195,210));y+=31
  if y==52:draw.text((overlay.width+14,y),'No structure hits',font=font,fill='white')
  legend.save(directory/(cid+'_sources_overlay.png'))
  pane=Image.open(directory/(cid+'.png')).convert('RGB');pane.thumbnail((640,610));panels.append((mode,pane,row['occlusion_pixel_ratio']))
 preview=Image.new('RGB',(1920,690),(20,25,35));draw=ImageDraw.Draw(preview)
 for i,(mode,pane,ratio) in enumerate(panels):
  draw.text((640*i+16,14),f'{cid} {mode} | occlusion {100*ratio:.4f}%',font=font,fill='white');preview.paste(pane,(640*i+(640-pane.width)//2,60+(610-pane.height)//2))
 (OUT/'comparisons').mkdir(exist_ok=True);preview.save(OUT/'comparisons'/(cid+'_three_modes.png'))
(OUT/'rtx_comparison.json').write_text(json.dumps(comparisons,indent=2))
keys=[k for k in comparisons[0] if k!='rtx_component_counts']
with (OUT/'rtx_comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in comparisons)
before=json.loads((ROOT/'reports/step2/frozen_before.json').read_text());omitted=[name for name in before if not (ROOT/name).exists() and (name=='reports/local_preflight.log' or '/sources/' in name or '/drawings/' in name or Path(name).suffix.lower() in ['.step','.stl'])];changed=[name for name,h in before.items() if name not in omitted and (not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h)]
assert not changed,changed
(ROOT/'reports/step2/frozen_after.json').write_text(json.dumps(dict(status='PASS',files_checked=len(before)-len(omitted),omitted_private_files=omitted,changed=changed,config_sha256=SHA),indent=2))
print(json.dumps([dict(camera_id=r['camera_id'],mode=r['mode'],IoU=r['mask_IoU'],delta=r['area_delta_pixels'],nonboundary=r['nonboundary_disagreement']) for r in comparisons],indent=2))
