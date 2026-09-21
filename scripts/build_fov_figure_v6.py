"""V6 plate: newly rendered native RGB with revised H/V optics, no image processing."""
import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
from matplotlib.transforms import Bbox

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/step2_1b_v6';REPORT=ROOT/'reports/step2_1b_v6';CONF=ROOT/'config/step2_1b_v6'
SOURCE=ROOT/'outputs/step2_1b_v6/raw';EXTERNAL=ROOT/'outputs/step2_1b_v3/debug'
GROUPS={'B':['C1','C0','C2'],'C':['C3','C5'],'D':['C4','C6']}
COLORS={'C0':'#1478AE','C1':'#21A78F','C2':'#D6AB45','C3':'#3969AD','C5':'#58B4C6','C4':'#A65252','C6':'#CB9167'}
W,H=4800,2700;INK='#24364B';MUTED='#596B7A'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 for folder in [OUT/'raw',OUT/'panels',REPORT,CONF]:folder.mkdir(parents=True,exist_ok=True)
 rigpath=ROOT/'config/rig_sim_v0.2.json';fitpath=ROOT/'config/step2_1b_v6/final_placement.json';rig=read(rigpath);p=read(fitpath);views=read(EXTERNAL/'external_views.json');records={r['camera_id']:r for r in p['camera_records']};R=np.array(p['R_world_B']);t=np.array(p['rig_translation_world_m'])
 fontpath=next(s for s in ['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'] if Path(s).exists());font_manager.fontManager.addfont(fontpath)
 plt.rcParams.update({'font.family':font_manager.FontProperties(fname=fontpath).get_name(),'font.size':14,'axes.unicode_minus':False,'svg.fonttype':'path','pdf.fonttype':42})
 manifest={};images={};image_axes=[];labels=[]
 for group,ids in GROUPS.items():
  for cid in ids:
   source=SOURCE/(cid+'.png');destination=OUT/'raw'/(cid+'.png')
   with Image.open(source) as im:im.load();images[cid]=np.asarray(im).copy();size=list(im.size);mode=im.mode
   expected=rig['optics']['front_main' if cid=='C0' else 'front_stereo' if cid in ['C1','C2'] else 'surround']['resolution'];assert size==expected and mode=='RGB',(cid,size,mode)
   assert source==destination
   status=read(REPORT/'render_status.json');assert status['status']=='PASS' and status['config_sha256']==sha(rigpath)
   manifest[cid]=dict(group=group,source=source.relative_to(ROOT).as_posix(),output=destination.relative_to(ROOT).as_posix(),sha256=sha(source),render_config_sha256=status['config_sha256'],resolution=size,mode=mode,copy_byte_identical=True)
 fig=plt.figure(figsize=(W/200,H/200),dpi=200,facecolor='white')
 def rect(x,y,w,h):return [x/W,1-(y+h)/H,w/W,h/H]
 def text(x,y,s,size=15,color=INK,weight='normal',ha='left'):
  artist=fig.text(x/W,1-y/H,s,fontsize=size,color=color,weight=weight,ha=ha,va='top');labels.append(artist);return artist
 def box(x,y,w,h):fig.add_artist(Rectangle((x/W,1-(y+h)/H),w/W,h/H,transform=fig.transFigure,facecolor='#F6F8FB',edgecolor='#DCE3EB',lw=1,zorder=-2))
 def pix(v,pts):
  a=(np.asarray(pts)-v['position_world_m'])@np.array(v['R_world_optical']);w,h=v['resolution'];return np.stack((w/2+v['fx_px']*a[...,0]/a[...,2],h/2+v['fy_px']*a[...,1]/a[...,2]),axis=-1)
 def capture(name,bounds):
  v=views[name];ax=fig.add_axes(rect(*bounds));w,h=v['resolution'];ax.imshow(Image.open(EXTERNAL/(name+'_rgba.png')),extent=[0,w,h,0]);ax.set_xlim(0,w);ax.set_ylim(h,0);ax.axis('off');return ax,v
 def raw_image(cid,bounds):
  x,y,bw,bh=bounds;im=images[cid];h,w=im.shape[:2];scale=min(bw/w,bh/h);dw,dh=w*scale,h*scale;actual=[x+(bw-dw)/2,y+(bh-dh)/2,dw,dh]
  ax=fig.add_axes(rect(*actual));artist=ax.imshow(im,origin='upper',interpolation='none',aspect='equal');ax.set_xlim(-.5,w-.5);ax.set_ylim(h-.5,-.5);ax.axis('off');assert np.array_equal(np.asarray(artist.get_array()),im)
  assert abs(dw/dh-w/h)<1e-12;assert len(ax.images)==1 and not ax.lines and not ax.patches and not ax.texts and not ax.collections
  manifest[cid]['plate_bounds_px']=actual;manifest[cid]['equal_scale']=scale;manifest[cid]['full_frame']=True;manifest[cid]['overlay_artists']=0;image_axes.append(ax)
 panels={'A':(80,180,2300,1120),'B':(2420,180,2300,1120),'C':(80,1340,2300,1320),'D':(2420,1340,2300,1320)}
 text(80,45,'七目头戴设备与七路相机成像',28,weight='bold')
 for bounds in panels.values():box(*bounds)
 x,y,_,_=panels['A'];text(x+40,y+28,'A  安装关系',21,weight='bold')
 ax,v=capture('body',(x+20,y+115,650,900));foot=p['floor']['z'];top=foot+p['worker']['final_height_m'];px=pix(v,np.array([[-.30,0,foot],[-.30,0,top]]));ax.annotate('',px[0],px[1],arrowprops=dict(arrowstyle='<->',color=INK,lw=1.5));q=px.mean(0);ax.text(q[0]-45,q[1],f"{p['worker']['final_height_m']:.3f} m",ha='right',va='center',fontsize=12,color=INK)
 ax,v=capture('head',(x+660,y+115,1570,900));offset={'C0':(0,150),'C1':(170,45),'C2':(-180,-5),'C3':(175,-135),'C5':(-200,-140),'C4':(200,175),'C6':(-265,185)}
 for cid in ['C0','C1','C2','C3','C4','C5','C6']:
  o=np.array(records[cid]['world_position_m']);e=o+.055*np.array(records[cid]['forward_world']);a,b=pix(v,np.array([o,e]));col=COLORS[cid];ax.scatter(*a,c=col,s=25,edgecolors='white',linewidths=.7,zorder=8);ax.annotate('',b,a,arrowprops=dict(arrowstyle='-|>',color=col,lw=1.7),zorder=8);ax.annotate(cid,a+np.array(offset[cid]),a,color=col,fontsize=13,weight='bold',ha='center',bbox=dict(facecolor='white',edgecolor='none',alpha=.92,pad=2),arrowprops=dict(arrowstyle='-',color=col,lw=.8),zorder=9)
 o=t+R@np.array([.045,-.15,-.08])
 for i,label in enumerate(['+X 前','+Y 左','+Z 上']):
  a,b=pix(v,np.array([o,o+R[:,i]*.045]));ax.annotate('',b,a,arrowprops=dict(arrowstyle='-|>',color=INK,lw=1.3));ax.text(*(b+np.array([-18,35]) if i==0 else b),label,fontsize=10,color=INK)
 text(x+40,y+1035,f"光心离地：前向 {records['C0']['height_above_floor_m']:.3f} m · 上视 {records['C3']['height_above_floor_m']:.3f} m · 下视 {records['C4']['height_above_floor_m']:.3f} m",13,color=MUTED)
 text(x+820,y+32,'B 坐标：+X 前 · +Y 佩戴者左 · +Z 上',13,color=MUTED)
 layout=rig['layout'];optics=rig['optics']
 for group,title in [('B','前向三目  C1 / C0 / C2'),('C','上视两目  C3 / C5'),('D','下视两目  C4 / C6')]:
  x,y,_,_=panels[group];text(x+40,y+28,group+'  '+title,21,weight='bold')
  if group=='B':
   text(x+40,y+108,f"光轴 +X · 左右总基线 {layout['front_baseline_mm']:g} mm",14,color=MUTED)
   for i,cid in enumerate(GROUPS[group]):
    xx=x+40+i*755;text(xx,y+200,cid,18,weight='bold');raw_image(cid,(xx,y+275,710,580))
   m=optics['front_main'];s=optics['front_stereo']
   text(x+40,y+935,f"C0：{m['resolution'][0]}×{m['resolution'][1]} · 针孔 · H{m['hfov_deg']:g}° / V{m['vfov_deg']:g}°",14)
   text(x+40,y+1010,f"C1/C2：{s['resolution'][0]}×{s['resolution'][1]} · 等距鱼眼 · H{s['hfov_deg']:g}° / V{s['vfov_deg']:g}°",14)
  else:
   direction='+Z' if group=='C' else '−Z';spacing=f"左右间距 {layout['surround_baseline_mm']:g} mm" if group=='C' else f"同侧上下间距 {2*layout['surround_z_half_mm']:g} mm"
   text(x+40,y+105,f'光轴 {direction} · {spacing}',14,color=MUTED)
   for i,cid in enumerate(GROUPS[group]):
    xx=x+40+i*1120;text(xx,y+160,cid,18,weight='bold');raw_image(cid,(xx,y+225,1080,960))
   s=optics['surround'];text(x+40,y+1240,f"{s['resolution'][0]}×{s['resolution'][1]} · 等距鱼眼 · H{s['hfov_deg']:g}° / V{s['vfov_deg']:g}°",13)
 # Basic layout checks only; no camera direction, visibility or simulation diagnostics.
 fig.canvas.draw();renderer=fig.canvas.get_renderer()
 for ax in image_axes:
  area=ax.get_window_extent(renderer)
  assert not any(area.overlaps(a.get_window_extent(renderer)) for a in labels),'Text crosses native RGB frame'
 assert len(image_axes)==7
 for ext in ['png','pdf','svg']:fig.savefig(OUT/('fov_overview_wearer_v6.'+ext),dpi=200,facecolor='white')
 svg=OUT/'fov_overview_wearer_v6.svg';svg.write_text('\n'.join(s.rstrip() for s in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
 for group,(x,y,w,h) in panels.items():fig.savefig(OUT/'panels'/('panel_'+group+'.png'),dpi=300,bbox_inches=Bbox.from_bounds(x/200,(H-y-h)/200,w/200,h/200),facecolor='white')
 plt.close(fig)
 sources=[rigpath,fitpath,EXTERNAL/'external_views.json',EXTERNAL/'body_rgba.png',EXTERNAL/'head_rgba.png']
 config=dict(baseline_commit='2c382882dbace7dbca5b34468b61552b3aabfc51',groups=GROUPS,canvas_px=[W,H],panels=panels,image_processing='none; proportional layout scaling only',camera_image_overlays=False,source_configuration={s.relative_to(ROOT).as_posix():sha(s) for s in sources},optics=rig['optics'],camera_height_above_floor_m={k:r['height_above_floor_m'] for k,r in records.items()})
 (CONF/'figure_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (REPORT/'image_manifest.json').write_text(json.dumps(dict(images=manifest,configuration=config['source_configuration'],meaning='New native per-camera RTX RGB with requested H/V optics; no RGB postwarp, exposure gain or overlays; complete rectangular frame',basic_checks=dict(seven_images=True,byte_identical_copies=True,equal_aspect_full_frames=True,no_image_overlay_artists=True,no_label_image_intersection=True),runtime='Layout of verified v6 native captures; A external render/physical geometry from unchanged v3. No overlap visualization or postprocessing.'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('V6 exported: PNG PDF SVG, seven byte-identical native RGB copies, four enlarged panels; basic layout checks PASS')
if __name__=='__main__':main()
