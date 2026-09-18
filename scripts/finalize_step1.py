"""Validate actual output artifacts, then produce review aids and an evidence manifest."""
import csv,hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs,pixel_rays

c=load_config();cams=camera_specs(c);out=ROOT/'outputs/step1'
sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
status=json.loads((out/'run_status.json').read_text())
assert status['status']=='PASS' and status['task']=='all',status
angles=json.loads((out/'angle_results.json').read_text())
assert len(angles)==22 and all(x['status']=='PASS' for x in angles)
entries=[]
for cam in cams:
    cid=cam['id'];o=cam['optics'];w,h=o['resolution']
    rgb=np.asarray(Image.open(out/f'ideal/{cid}.png'))
    mask=np.asarray(Image.open(out/f'ideal/{cid}_valid_mask.png'))
    metadata=json.loads((out/f'ideal/{cid}.json').read_text())
    assert rgb.shape==(h,w,3) and mask.shape==(h,w)
    assert metadata['config_sha256']==sha and metadata['projection']==o
    assert metadata['simulation_time_seconds']==0. and metadata['mode']=='ideal'
    _,expected=pixel_rays(cam)
    assert np.array_equal(mask,expected.astype(np.uint8)*255)
    assert not np.any(rgb[~expected])
    assert rgb[expected].std()>10,('uniform image',cid)
    entries.append(dict(camera_id=cid,resolution=[w,h],mode='ideal',simulation_time_seconds=0.,
        image=f'ideal/{cid}.png',mask=f'ideal/{cid}_valid_mask.png',metadata=f'ideal/{cid}.json'))
for row in angles:
    cid=row['camera_id'];cam=next(v for v in cams if v['id']==cid)
    image=ROOT/row['image'];assert image.exists()
    assert Image.open(image).size==tuple(cam['optics']['resolution'])
    row.update(version=c['design_revision'],config_sha256=sha,resolution=cam['optics']['resolution'],
               projection_model=cam['optics']['model'],backend='native OpenCV pinhole' if cid=='C0' else 'legacy RTX fisheyePolynomial',
               raw_image=str(image.with_name(image.stem+'_raw.png').relative_to(ROOT)))
(out/'angle_results.json').write_text(json.dumps(angles,indent=2))
fields=['camera_id','name','angle_deg','azimuth_deg','theoretical_visible','theoretical_uv_px','actual_visible','detected_uv_px','residual_px','status','image']
with (out/'angle_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fields,extrasaction='ignore');writer.writeheader();writer.writerows(angles)

font_paths=['C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
font_path=next((p for p in font_paths if Path(p).exists()),None)
font=ImageFont.truetype(font_path,23) if font_path else ImageFont.load_default()
overview_meta=json.loads((out/'worn_overview.json').read_text())
overview=Image.open(out/'worn_overview_raw.png').convert('RGB');od=ImageDraw.Draw(overview)
od.rectangle((0,0,1600,120),fill=(18,28,42))
od.text((30,23),'SIM-V0.2-vfov130 | worn | nominal simulation structure',font=font,fill='white')
od.text((30,65),'Dots: optical centers  /  arrows: optical axes  /  labels: post-render annotation',font=font,fill=(198,214,233))
R=np.array(overview_meta['camera_R_world_optical']);pos=np.array(overview_meta['camera_position_world_m'])
def overview_pixel(world):
    d=R.T@(world-pos)
    return np.array([800+(1600*42/36)*d[0]/d[2],600+(1200*42/27)*d[1]/d[2]])
markers=[]
colors=[(191,54,47),(23,111,177),(6,127,79),(140,63,183),(154,95,18),(12,124,134),(187,46,119)]
for cam,color in zip(cams,colors):
    center=np.array(cam['position_mm'])*.001+c['simulation']['rig_world_translation_m']
    dot=overview_pixel(center);tip=overview_pixel(center+np.array(cam['forward_B'])*.035)
    markers.append((cam,color,dot,tip))
for i,(cam,color,dot,tip) in enumerate(sorted(markers,key=lambda m:m[2][1])):
    anchor=(1210,245+i*90);u,v=dot
    od.line([tuple(dot),(1160,anchor[1]+21),anchor],fill=color,width=2)
    od.line([tuple(dot),tuple(tip)],fill=color,width=4)
    direction=(tip-dot)/np.linalg.norm(tip-dot);side=np.array([-direction[1],direction[0]])
    od.polygon([tuple(tip),tuple(tip-12*direction+5*side),tuple(tip-12*direction-5*side)],fill=color)
    od.ellipse((u-6,v-6,u+6,v+6),fill=color,outline='white',width=2)
    od.rounded_rectangle((anchor[0],anchor[1],anchor[0]+325,anchor[1]+48),radius=5,fill=(245,248,252),outline=color,width=2)
    direction_text='front +X' if cam['id'] in ('C0','C1','C2') else 'up +Z' if cam['id'] in ('C3','C5') else 'down -Z'
    od.text((anchor[0]+12,anchor[1]+9),cam['id']+'  '+direction_text,fill=color,font=font)
overview.save(out/'worn_overview.png')
overview_meta.update(intrinsics_px=dict(fx=1600*42/36,fy=1200*42/27,cx=800,cy=600),annotation_script='scripts/finalize_step1.py')
(out/'worn_overview.json').write_text(json.dumps(overview_meta,indent=2))
preview=Image.new('RGB',(1440,1080),(20,24,32));draw=ImageDraw.Draw(preview)
positions=[(0,0),(480,0),(960,0),(0,360),(480,360),(0,720),(480,720)]
for cam,(x,y) in zip(cams,positions):
    pic=Image.open(out/f'ideal/{cam["id"]}.png');pic.thumbnail((460,310))
    preview.paste(pic,(x+(480-pic.width)//2,y+42));draw.text((x+16,y+10),cam['id'],fill='white',font=font)
for y,line in [(480,'Seven cameras'),(520,'ideal / static t=0'),(560,c['design_revision']),(640,'Black corners:'),(680,'outside valid image circle')]:
    draw.text((1000,y),line,fill='white',font=font)
preview.save(out/'seven_camera_preview.png')

# A compact inspection sheet of independently detected targets; full images remain authoritative.
sheet=Image.new('RGB',(1320,1120),(18,22,30));draw=ImageDraw.Draw(sheet)
draw.text((22,15),'Rendered angle checks | magnified measured target patches | full frames in angles/',fill='white',font=font)
for i,row in enumerate(angles):
    x=(i%3)*440;y=65+(i//3)*130
    draw.text((x+10,y),row['camera_id']+' '+row['name'],fill='white',font=font)
    if row['detected_uv_px']:
        u,v=row['detected_uv_px'];im=Image.open(ROOT/row['image'])
        patch=im.crop((round(u)-9,round(v)-9,round(u)+9,round(v)+9)).resize((72,72),Image.Resampling.NEAREST)
        sheet.paste(patch,(x+12,y+36))
        draw.text((x+100,y+40),f'residual {row["residual_px"]:.3f} px',fill=(153,227,183),font=font)
    else:draw.text((x+12,y+44),'Outside: no target detected',fill=(153,227,183),font=font)
sheet.save(out/'angle_checks_preview.png')

assert Image.open(out/'worn_overview.png').size==(1600,1200)
maximum=max(r['residual_px'] or 0 for r in angles)
manifest=dict(version=c['design_revision'],config_sha256=sha,status='PASS',
    artifact_checks='7 native RGB/masks/metadata + overview + 22 rendered angle cases verified',
    offline=json.loads((ROOT/'reports/offline_results.json').read_text()),angle_checks=22,max_residual_px=maximum,
    frames=entries,limitations=['sequential static capture, not parallel 30 FPS','no hardware synchronization validation','IMU mount only','no SLAM/VIO','legacy RTX ftheta on Isaac 6.0.1.0'],
    files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and 'diagnostics' not in p.parts and p.name!='manifest.json'})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(ROOT/'reports/artifact_checks.json').write_text(json.dumps(dict(status='PASS',cameras=7,angle_checks=22,max_residual_px=maximum,config_sha256=sha),indent=2))
print(json.dumps(dict(status='PASS',cameras=7,angle_checks=22,max_residual_px=maximum)))
