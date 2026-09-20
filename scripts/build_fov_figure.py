"""Single technical figure: real external RTX rasters plus projection-derived vectors."""
import sys,json,hashlib,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle
from matplotlib import font_manager
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs
from projection import unproject,project
OUT=ROOT/'outputs/step2_1b';DEBUG=OUT/'debug';REPORT=ROOT/'reports/step2_1b'
manifest=json.loads((REPORT/'input_manifest.json').read_text())
for name,digest in manifest.items():
 assert hashlib.sha256((ROOT/name).read_text(encoding='utf-8-sig').replace('\r\n','\n').rstrip().encode()).hexdigest()==digest,('Frozen input differs',name)
before=json.loads((REPORT/'frozen_before.json').read_text(encoding='utf-8'))
changed=[name for name,digest in before.items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
assert not changed,changed
fontpath=next(p for p in ['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'] if Path(p).exists())
font_manager.fontManager.addfont(fontpath)
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=fontpath).get_name(),'font.size':12,'axes.unicode_minus':False,'svg.fonttype':'path','pdf.fonttype':42})
placement=json.loads((ROOT/'outputs/step2_1/placement.json').read_text());views=json.loads((DEBUG/'external_views.json').read_text());status=json.loads((DEBUG/'render_status.json').read_text());assert status['status']=='PASS' and status['formal_sensor_frames']==0
specs={c['id']:c for c in camera_specs(load_config())};records={r['camera_id']:r for r in placement['camera_records']};R=np.array(placement['R_world_B']);COLORS={'C0':'#0875b7','C1':'#009a8c','C2':'#c28015','C3':'#9b58b3','C4':'#315aaa','C5':'#cd6661','C6':'#579444'}
fig=plt.figure(figsize=(24,17),dpi=200,facecolor='white');W,H=4800,3400
INK='#203147';MUTED='#59697b';LIGHT='#dce3eb'
def rect(x,y,w,h):return [x/W,1-(y+h)/H,w/W,h/H]
def text(x,y,s,size=14,color=INK,weight='normal',ha='left'):
 return fig.text(x/W,1-y/H,s,fontsize=size,color=color,weight=weight,ha=ha,va='top')
def box(x,y,w,h,color='#f3f6fa'):
 fig.add_artist(Rectangle((x/W,1-(y+h)/H),w/W,h/H,transform=fig.transFigure,facecolor=color,edgecolor='none',zorder=-1))
def pixel(v,points):
 a=(np.asarray(points)-v['position_world_m'])@np.array(v['R_world_optical']);w,h=v['resolution'];assert np.all(a[...,2]>0)
 return np.stack((w/2+v['fx_px']*a[...,0]/a[...,2],h/2+v['fy_px']*a[...,1]/a[...,2]),axis=-1)
def boundary_uv(c,n=128):
 o=c['optics'];a=np.linspace(0,2*np.pi,n,endpoint=False);co=np.cos(a);si=np.sin(a)
 rad=np.minimum(np.divide(o['resolution'][0]/2,np.abs(co),out=np.full(n,np.inf),where=np.abs(co)>1e-12),np.divide(o['resolution'][1]/2,np.abs(si),out=np.full(n,np.inf),where=np.abs(si)>1e-12))
 if o['valid_radius_px'] is not None:rad=np.minimum(rad,o['valid_radius_px'])
 return np.stack([co*rad+o['cx_px'],si*rad+o['cy_px']],axis=-1)
def rays(c,uv):return unproject(c,uv)@(R@np.array(c['R_B_optical'])).T
def world(c,uv,length):return np.array(records[c['id']]['world_position_m'])+length*rays(c,uv)
# Check continuous image-edge boundaries and their round trips, including >90 degree directions.
checks={}
for cid,c in specs.items():
 uv=boundary_uv(c);rr=unproject(c,uv);p,valid=project(c,rr);err=float(np.max(np.abs(p-uv)));theta=np.rad2deg(np.arccos(np.clip(rr[:,2],-1,1)));assert err<1e-8
 if cid in ['C3','C4','C5','C6']:assert np.allclose(theta,110) and np.all(rr[:,2]<0)
 if cid in ['C0','C1','C2']:
  o=c['optics'];edge=unproject(c,[[o['resolution'][0],o['cy_px']],[o['cx_px'],o['resolution'][1]]]);measured=2*np.rad2deg(np.arccos(np.clip(edge[:,2],-1,1)));assert np.allclose(measured,[o['hfov_deg'],o['vfov_deg']])
 checks[cid]={'samples':len(uv),'roundtrip_max_px':err,'boundary_theta_min_deg':float(theta.min()),'boundary_theta_max_deg':float(theta.max()),'world_optical_axis':(R@np.array(c['forward_B'])).tolist(),'position_world_m':records[cid]['world_position_m']}
examples=json.loads((DEBUG/'intersection_examples.json').read_text());chosen={}
for cid in ['C3','C4','C5','C6']:
 pool=[a for a in examples if a['camera_id']==cid and a['hit_path'].startswith('/World/Person') and .008<a['distance_m']<.32]
 # A near-grazing ray illustrates continuation behind the first actual surface hit.
 chosen[cid]=min(pool,key=lambda a:(a['theta_deg'],a['phi_deg']))
chosen_device=next(a for a in examples if a['camera_id']=='C3' and a['hit_path'].endswith('/central_housing') and a['distance_m']<.20)
def panel(name,xywh,ids,length,labels,alpha=.04,show_hits=True):
 v=views[name];ax=fig.add_axes(rect(*xywh));w,h=v['resolution'];ax.imshow(Image.open(DEBUG/(name+'_rgba.png')),extent=[0,w,h,0]);ax.set_xlim(0,w);ax.set_ylim(h,0);ax.set_aspect('equal');ax.axis('off')
 faces=[]
 for cid in ids:
  c=specs[cid];uv=boundary_uv(c);center=np.array([c['optics']['cx_px'],c['optics']['cy_px']]);origin=np.array(records[cid]['world_position_m']);col=COLORS[cid]
  rings=[world(c,center+(uv-center)*fraction,length) for fraction in np.linspace(0,1,7)]
  for j in range(6):
   for k in range(len(uv)):
    kk=(k+1)%len(uv);poly=np.array([rings[j][k],rings[j+1][k],rings[j+1][kk],rings[j][kk]])
    depth=np.mean((poly-v['position_world_m'])@np.array(v['R_world_optical'])[:,2]);faces.append((depth,pixel(v,poly),col))
  edge=pixel(v,np.vstack([rings[-1],rings[-1][0]]));ax.plot(*edge.T,color=col,lw=1.25,alpha=.8,zorder=3)
  # Meridians are actual unprojected image radial curves; the cap can extend behind the camera.
  for k in [0,32,64,96]:
   curve=world(c,center+(uv[k]-center)*np.linspace(0,1,70)[:,None],length);q=pixel(v,curve);ax.plot(*q.T,color=col,lw=.85,alpha=.65,zorder=3)
   q=pixel(v,[origin,curve[-1]]);ax.plot(*q.T,color=col,lw=.7,alpha=.32,zorder=3)
  if cid in ['C3','C4','C5','C6']:
   az=np.linspace(0,2*np.pi,129);o=c['optics'];equator=np.stack([o['cx_px']+o['fx_px']*np.pi/2*np.cos(az),o['cy_px']+o['fx_px']*np.pi/2*np.sin(az)],axis=-1);q=pixel(v,world(c,equator,length));ax.plot(*q.T,color=col,lw=.65,ls=(0,(3,5)),alpha=.65,zorder=3)
  q=pixel(v,[origin,origin+np.array(records[cid]['forward_world'])*length*.70]);ax.annotate('',xy=q[1],xytext=q[0],arrowprops=dict(arrowstyle='-|>',color=col,lw=2.1,mutation_scale=16),zorder=7)
  dot=pixel(v,origin);ax.scatter(*dot,s=20,c=col,edgecolor='white',linewidth=.8,zorder=8)
  if cid in labels:
   loc=labels[cid];axis='+X' if cid in ['C0','C1','C2'] else '+Z' if cid in ['C3','C5'] else '-Z'
   ax.annotate(cid+'  '+axis,xy=dot,xytext=loc,color=col,fontsize=13,weight='bold',va='center',arrowprops=dict(arrowstyle='-',color=col,lw=.85),bbox=dict(boxstyle='round,pad=.17',facecolor='white',edgecolor='none',alpha=.92),zorder=10)
  if show_hits and cid in chosen:
   a=chosen[cid];d=np.array(a['direction']);hit=np.array(a['hit_world']);end=origin+d*length;q=pixel(v,[origin,hit,end]);ax.plot(*q[:2].T,color=col,lw=1.2,zorder=7);ax.plot(*q[1:].T,color='#46505e',lw=1.15,ls=(0,(3,3)),zorder=7);ax.scatter(*q[1],s=24,c='#243241',marker='x',linewidths=1.6,zorder=9)
 if show_hits and 'C3' in ids:
  a=chosen_device;origin=np.array(a['origin']);hit=np.array(a['hit_world']);end=origin+np.array(a['direction'])*length;q=pixel(v,[origin,hit,end]);ax.plot(*q[:2].T,color=COLORS['C3'],lw=1.1,zorder=7);ax.plot(*q[1:].T,color='#46505e',lw=1.1,ls=(0,(3,3)),zorder=7);ax.scatter(*q[1],s=22,c='#243241',marker='s',edgecolor='white',linewidths=.5,zorder=9)
 faces.sort(key=lambda a:-a[0]);ax.add_collection(PolyCollection([f[1] for f in faces],facecolors=[f[2] for f in faces],edgecolors='none',alpha=alpha,zorder=2))
 return ax
text(110,78,'1.8 m 人体佩戴条件下七相机视场范围示意图',30,weight='bold')
text(114,190,'Step 2.1b  /  NVIDIA Office + Male Doctor  /  基线 a77f57b  /  实际佩戴位姿与七目参数冻结',13,color=MUTED)
box(110,295,2520,80);text(140,311,'A   整体佩戴与七目包络',18,weight='bold')
main=panel('main',(110,400,2520,2300),list(specs),.46,{'C1':(85,275),'C0':(85,365),'C2':(85,455),'C3':(1480,190),'C5':(1480,290),'C4':(1480,700),'C6':(1480,800)},alpha=.032)
# Coordinate triad shares the exact external projection; the anchor is for annotation only.
v=views['main'];anchor=np.array(v['target']);q0=np.array([245,1230]);projected_anchor=pixel(v,anchor)
for axis,vec,col in [('+X 前方',R[:,0],'#394c65'),('+Y 佩戴者左',R[:,1],'#394c65'),('+Z 上方',R[:,2],'#394c65')]:
 q1=q0+pixel(v,anchor+vec*.14)-projected_anchor;main.annotate('',xy=q1,xytext=q0,arrowprops=dict(arrowstyle='-|>',lw=1.5,color=col),zorder=10);main.text(q1[0],q1[1]-12,axis,fontsize=11,color=col,ha='center',va='bottom',zorder=10)
main.text(65,1540,'完整人物高 1.800 m\n光心离地：前向 1.7314 m\n上视 1.7514 m / 下视 1.7114 m',fontsize=12,color=INK,linespacing=1.7,bbox=dict(facecolor='white',edgecolor='none',alpha=.92))
box(2770,295,1930,80);text(2800,311,'B   前向三目：C1 / C0 / C2',18,weight='bold')
text(2790,393,'三条光轴平行朝 +X；副相机不向两侧外撇',13,color=MUTED)
front=panel('front',(2770,470,1930,1030),['C1','C0','C2'],.28,{'C1':(1350,290),'C0':(1320,435),'C2':(1320,580)},alpha=.065,show_hits=False)
text(2790,1490,'C0：独立 fx/fy 针孔；C1/C2：圆 ∩ 画幅；基线 63 mm',12,color=MUTED)
box(2770,1610,1930,80);text(2800,1626,'C   四目环视：前额组件的上、下两组',18,weight='bold')
text(2800,1720,'C3 / C5  上视 +Z',15,weight='bold');text(3820,1720,'C4 / C6  下视 -Z',15,weight='bold')
up=panel('up',(2770,1840,930,920),['C3','C5'],.27,{'C3':(690,160),'C5':(65,245)},alpha=.085)
down=panel('down',(3770,1840,930,920),['C4','C6'],.32,{'C4':(675,780),'C6':(65,860)},alpha=.085)
text(2800,1780,'头顶 / 天花板方向',11,color=MUTED);text(3820,1780,'身体前下方 / 地面方向',11,color=MUTED)
text(2790,2800,'全角 220°，离轴至 110°；细虚线为 90° 参考环',12,color=MUTED)
# Footer: compact parameter table and explicit interpretation of the geometric overlay.
box(110,2890,2520,365);text(145,2910,'投影参数（来自冻结配置）',15,weight='bold')
for y,parts in zip([2990,3060,3130],[['C0','1920×1080','针孔 120°×130°'],['C1 / C2','1600×1300','等距 160°×130°'],['C3-C6','1080×960','等距圆形 220° / 有效直径 960 px']]):
 for x,s in zip([150,570,1180],parts):text(x,y,s,13)
text(150,3210,'图中包络按有限长度截断，仅用于显示，不代表相机量程。',11,color=MUTED)
text(2790,2920,'图例与边界',15,weight='bold')
text(2790,2990,'彩色半透明面 / 浅色轮廓：理想视场包络',12)
text(2790,3050,'深色实体：设备；人物实体：真实蒙皮佩戴者',12)
text(2790,3110,'× 人体首交点 / ■ 设备首交点；粗虚线为被遮挡延伸',12)
text(2790,3170,'穿插表示潜在遮挡；未绘制精确遮挡边界或占比。',12,color=MUTED)
text(114,3310,'基于 Step 2.1 真实佩戴位姿，仅说明单摄像头空域与遮挡；不代表联合覆盖率或 SLAM 结果。',12,color=MUTED)
text(4690,3310,'头带穿模按基线保留，佩戴适配未通过。',12,color='#965c31',ha='right')
for suffix in ['png','pdf','svg']:fig.savefig(OUT/('fov_overview_wearer.'+suffix),dpi=200,facecolor='white')
svg=OUT/'fov_overview_wearer.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
plt.close(fig)
(REPORT/'projection_checks.json').write_text(json.dumps({'status':'PASS','boundary_checks':checks,'chosen_intersections':chosen,'device_intersection':chosen_device,'display_lengths_m':{'main':.46,'front':.28,'up':.27,'down':.32},'notes':'Finite radial display caps, not sensor range. Sample intersections are not occlusion statistics.'},indent=2))
(REPORT/'validation.json').write_text(json.dumps({'status':'PASS','baseline_commit':status['baseline_commit'],'frozen_files_checked':len(before),'frozen_changed':changed,'external_frames':status['external_frames'],'formal_sensor_frames_rendered':0,'person_height_m':status['person_height_m'],'camera_transforms_match_step21':True,'boundary_projection_roundtrip':True,'fisheye_max_off_axis_deg':110,'png_resolution':[4800,3400],'headband_fit':'Known Step 2.1 intersection preserved; not repaired or passed','visual_review':'See fov_figure_report.md'},indent=2))
print('Wrote main PNG/PDF/SVG; frozen files unchanged:',len(before))
