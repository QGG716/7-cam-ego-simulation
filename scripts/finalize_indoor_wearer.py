"""Small post-render presentation and checks; never edits native sensor images."""
import json,csv,hashlib,math,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/step2_1'
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from rig_common import load_config,camera_specs,geometry_specs,pixel_rays
from analyze_step2 import inside  # Pure helper; its run() is guarded by __main__.
fontpath=next((p for p in ['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if Path(p).exists()),None)
def font(n):return ImageFont.truetype(fontpath,n) if fontpath else ImageFont.load_default()
F=font(25);small=font(21);big=font(34);bg=(18,24,34)
place=json.loads((OUT/'placement.json').read_text());cfg=json.loads((ROOT/'config/indoor_wearer_180.json').read_text());rows=json.loads((OUT/'occlusion_summary.json').read_text())
sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest();assert sha==place['config_sha256'];assert abs(place['person_height_after_m']-1.8)<2e-6;assert place['rig_scale']==1
specs={c['id']:c for c in camera_specs(load_config())}
assert len(rows)==21 and {(r['camera_id'],r['mode']) for r in rows}=={(cid,mode) for cid in specs for mode in cfg['mode_order']}
inside_records=[(c['id'],g['name']) for c in specs.values() for g in geometry_specs(load_config()) if g['group']!='Wearer' and inside(c['position_mm'],g)]
assert not inside_records,inside_records
pos={c['camera_id']:np.array(c['world_position_m']) for c in place['camera_records']}
baselines={a+'_'+b:float(np.linalg.norm(pos[a]-pos[b])*1000) for a,b in [('C1','C2'),('C3','C5'),('C4','C6'),('C3','C4'),('C5','C6')]}
assert np.allclose(list(baselines.values()),[63,110,110,40,40],atol=1e-6)
colors={0:(0,0,0),1:(235,93,57),2:(239,195,45),3:(177,90,221),4:(48,118,175),5:(140,140,140)}
def fit(canvas,pic,box):
 x,y,w,h=box;pic=pic.copy();pic.thumbnail((w,h));canvas.paste(pic,(x+(w-pic.width)//2,y+(h-pic.height)//2))
def getrow(cid,mode):return next(r for r in rows if r['camera_id']==cid and r['mode']==mode)
for row in rows:
 cid=row['camera_id'];mode=row['mode'];meta=json.loads((OUT/mode/(cid+'.json')).read_text());rgb=Image.open(OUT/mode/(cid+'.png')).convert('RGB');labels=np.load(OUT/mode/(cid+'_labels.npz'));valid=labels['valid'];classes=labels['classes'];assert rgb.size==tuple(meta['resolution']);assert valid.shape==classes.shape==tuple(meta['resolution'][::-1]);assert meta['config_sha256']==sha and meta['time_seconds']==0 and meta['original_ellipsoid_hidden']
 _,expected_valid=pixel_rays(specs[cid]);assert np.array_equal(valid,expected_valid);assert meta['projection']==specs[cid]['optics'];assert meta['placement']==place['camera_records'][int(cid[1])];assert meta['same_render_product_rgb_labels'];assert meta['lighting']==place['lighting']
 raw=np.array(Image.open(OUT/mode/(cid+'_raw.png')).convert('RGB'));assert np.array_equal(raw[valid],np.array(rgb)[valid])
 for name,code in cfg['class_codes'].items():assert row['counts'][name]==int((classes==code).sum())
 assert int(valid.sum())==row['N_valid'];assert sum(v for k,v in row['counts'].items() if k!='INVALID')==row['N_valid'];assert not classes[~valid].any()
 if mode=='room_only':assert not np.isin(classes,[1,2,3]).any()
 if mode=='device_only':assert not (classes==3).any()
 color=np.zeros((*classes.shape,3),np.uint8)
 for code,col in colors.items():color[classes==code]=col
 arr=np.array(rgb);occupied=np.isin(classes,[1,2,3]);arr[occupied]=(arr[occupied]*.35+color[occupied]*.65).astype(np.uint8);arr[~valid]=0
 Image.fromarray(arr).save(OUT/mode/(cid+'_overlay.png'))
keys=['camera_id','mode','N_valid','device_pixels','mount_pixels','wearer_pixels','environment_pixels','unknown_pixels','device_ratio','mount_ratio','wearer_ratio','environment_ratio','unknown_ratio']
with (OUT/'occlusion_summary.csv').open('w',newline='',encoding='utf-8') as f:
 writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
 for r in rows:
  d={k:r[k] for k in ['camera_id','mode','N_valid']}
  for title,code in [('device','DEVICE'),('mount','MOUNT'),('wearer','WEARER'),('environment','ENVIRONMENT'),('unknown','UNKNOWN_OR_NO_HIT')]:d[title+'_pixels']=r['counts'][code];d[title+'_ratio']=r['ratios'][code]
  writer.writerow(d)
for name,ids,ncols,panel in [('front_trio',['C1','C0','C2'],3,(800,780)),('surround_four',['C3','C5','C4','C6'],2,(800,790))]:
 canvas=Image.new('RGB',(panel[0]*ncols,panel[1]*math.ceil(len(ids)/ncols)),bg);draw=ImageDraw.Draw(canvas)
 for i,cid in enumerate(ids):
  x=(i%ncols)*panel[0];y=(i//ncols)*panel[1];r=getrow(cid,'worn_full');draw.text((x+20,y+12),cid+' | worn_full',font=big,fill='white');draw.text((x+20,y+58),f'Device {100*r["ratios"]["DEVICE"]:.2f}% / Mount {100*r["ratios"]["MOUNT"]:.2f}% / Person {100*r["ratios"]["WEARER"]:.2f}%',font=small,fill=(190,210,230));fit(canvas,Image.open(OUT/'worn_full'/(cid+'.png')),(x+10,y+103,panel[0]-20,panel[1]-113))
 canvas.save(OUT/(name+'.png'))
# Project known optical centers and axes onto external rendered views only.
for p in (OUT/'overview').glob('*_raw.png'):
 name=p.stem[:-4];meta=json.loads((p.parent/(name+'.json')).read_text());image=Image.open(p).convert('RGB');draw=ImageDraw.Draw(image);pos=np.array(meta['position_world_m']);R=np.array(meta['R_world_optical']);w,h=meta['resolution']
 def pixel(point):
  v=R.T@(np.array(point)-pos);return np.array([w/2+meta['fx_px']*v[0]/v[2],h/2+meta['fy_px']*v[1]/v[2]])
 draw.rectangle((0,0,w,78),fill=bg);draw.text((22,17),name+' | 1.800 m wearer | optical centers and axes (post-render)',font=F,fill='white')
 for i,c in enumerate(place['camera_records']):
  col=tuple(int(x) for x in [(245,84,64),(70,175,245),(65,215,150),(222,159,245),(255,210,60),(120,220,225),(248,129,182)][i]);dot=pixel(c['world_position_m']);tip=pixel(np.array(c['world_position_m'])+np.array(c['forward_world'])*.035)
  if not (0<dot[0]<w and 0<dot[1]<h):continue
  anchor=np.array([40 if i<4 else w-280,120+(i if i<4 else i-4)*88]);draw.line([tuple(dot),tuple(tip)],fill=col,width=4);v=tip-dot;v/=max(np.linalg.norm(v),1);perp=np.array([-v[1],v[0]]);draw.polygon([tuple(tip),tuple(tip-v*12+perp*5),tuple(tip-v*12-perp*5)],fill=col);draw.ellipse((dot[0]-5,dot[1]-5,dot[0]+5,dot[1]+5),fill=col);draw.line([tuple(dot),tuple(anchor+[0,16])],fill=col,width=2);draw.text(tuple(anchor),c['camera_id']+'  h='+f'{c["height_above_floor_m"]:.4f} m',font=F,fill=col,stroke_width=1,stroke_fill='black')
 image.save(p.parent/(name+'.png'))
obsfile=ROOT/'reports/step2_1/observations.json'
if obsfile.exists():
 obs=json.loads(obsfile.read_text(encoding='utf-8'));cards=OUT/'camera_cards';cards.mkdir(exist_ok=True)
 for c in place['camera_records']:
  cid=c['camera_id'];r=getrow(cid,'worn_full');im=Image.new('RGB',(2400,2000),bg);draw=ImageDraw.Draw(im);draw.text((30,18),cid+' | Office / Male Doctor / 1.800 m',font=big,fill='white')
  fit(im,Image.open(OUT/'worn_full'/(cid+'.png')),(25,85,1400,980));fit(im,Image.open(OUT/'worn_full'/(cid+'_overlay.png')),(1460,85,910,800))
  lines=[f'Height above floor: {c["height_above_floor_m"]:.6f} m',f'Optical axis: {np.round(c["forward_world"], 6).tolist()}',f'Image up: {np.round(c["image_up_world"], 6).tolist()}',('H120 / V130 pinhole, independent fx/fy' if cid=='C0' else 'H160 / V130 equidistant' if cid in ['C1','C2'] else '220 deg full circular equidistant'),f'Device {r["ratios"]["DEVICE"]*100:.4f}% / Mount {r["ratios"]["MOUNT"]*100:.4f}%',f'Person {r["ratios"]["WEARER"]*100:.4f}% / N_valid {r["N_valid"]}','Overlay: red=device; yellow=mount; purple=person']
  for j,line in enumerate(lines):draw.text((1460,920+j*40),line,font=small,fill='white')
  for i,mode in enumerate(['room_only','device_only','worn_full']):
   draw.text((i*800+25,1260),mode,font=F,fill='white');fit(im,Image.open(OUT/mode/(cid+'.png')),(i*800+10,1310,780,510))
  import textwrap
  for j,line in enumerate(textwrap.wrap(obs[cid],width=66)):draw.text((30,1850+j*38),line,font=F,fill='white')
  im.save(cards/(cid+'.png'))
before=json.loads((ROOT/'reports/step2_1/frozen_before.json').read_text(encoding='utf-8'))
# Public clones intentionally omit private source/review files, never tracked results.
omitted=[name for name in before if not (ROOT/name).exists() and ('/sources/' in name or '/drawings/' in name or name.startswith(('reports/source_review/','reports/preflight_initial/')) or name=='reports/local_preflight.log' or Path(name).suffix.lower() in ['.step','.stl'])]
changed=[name for name,h in before.items() if name not in omitted and (not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h)];assert not changed,changed
(ROOT/'reports/step2_1/validation.json').write_text(json.dumps(dict(status='PASS',native_frames=len(rows),person_height_m=place['person_height_after_m'],config_sha256=sha,frozen_files_checked=len(before)-len(omitted),omitted_private_files=omitted,frozen_changed=changed,baselines_mm=baselines,optical_centers_inside_device=inside_records,RGB_labels_same_product=True,notes='Placement fit and actual visible content require visual review; no FPS/SLAM verification'),indent=2))
print('Validated frames',len(rows),'frozen files',len(before))
