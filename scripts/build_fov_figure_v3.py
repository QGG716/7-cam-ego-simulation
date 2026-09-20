"""A/B/C/D technical plate with actual scene RGB and measured-depth overlap shading."""
import sys,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle,Patch
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.transforms import Bbox
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs
from projection import unproject
from scene_overlap_v3 import COLORS,boundary_uv,run,SOFT
run()
OUT=ROOT/'outputs/step2_1b_v3';DEBUG=OUT/'debug';REPORT=ROOT/'reports/step2_1b_v3';(OUT/'panels').mkdir(exist_ok=True)
p=json.loads((ROOT/'config/step2_1b_v3/final_placement.json').read_text());cfg=json.loads((ROOT/'config/step2_1b_v3/figure_config.json').read_text());views=json.loads((DEBUG/'external_views.json').read_text());status=json.loads((DEBUG/'render_status.json').read_text());assert status['status']=='PASS'
fontpath=next(x for x in ['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'] if Path(x).exists());font_manager.fontManager.addfont(fontpath)
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=fontpath).get_name(),'font.size':14,'axes.unicode_minus':False,'svg.fonttype':'path','pdf.fonttype':42})
specs={c['id']:c for c in camera_specs(load_config())};records={r['camera_id']:r for r in p['camera_records']};R=np.array(p['R_world_B']);t=np.array(p['rig_translation_world_m']);INK='#24364B';MUTED='#596B7A';W,H=4800,3800
fig=plt.figure(figsize=(24,19),dpi=200,facecolor='white')
def rect(x,y,w,h):return [x/W,1-(y+h)/H,w/W,h/H]
def text(x,y,s,size=15,color=INK,weight='normal',ha='left'):
 return fig.text(x/W,1-y/H,s,fontsize=size,color=color,weight=weight,ha=ha,va='top')
def box(x,y,w,h):fig.add_artist(Rectangle((x/W,1-(y+h)/H),w/W,h/H,transform=fig.transFigure,facecolor='#F6F8FB',edgecolor='#DCE3EB',lw=1,zorder=-2))
def pix(v,pts):
 a=(np.asarray(pts)-v['position_world_m'])@np.array(v['R_world_optical']);w,h=v['resolution'];return np.stack((w/2+v['fx_px']*a[...,0]/a[...,2],h/2+v['fy_px']*a[...,1]/a[...,2]),axis=-1)
def capture(name,bounds):
 v=views[name];ax=fig.add_axes(rect(*bounds));w,h=v['resolution'];ax.imshow(Image.open(DEBUG/(name+'_rgba.png')),extent=[0,w,h,0]);ax.set_xlim(0,w);ax.set_ylim(h,0);ax.axis('off');return ax,v
labeloffset={'C0':(0,150),'C1':(170,45),'C2':(-180,35),'C3':(175,-135),'C5':(-200,-140),'C4':(200,175),'C6':(-240,155)}
def axes(ax,v,ids,length=.06,labels=True):
 for cid in ids:
  o=np.array(records[cid]['world_position_m']);e=o+length*np.array(records[cid]['forward_world']);a,b=pix(v,np.array([o,e]));col=COLORS[cid];ax.scatter(*a,c=col,s=25,edgecolors='white',linewidths=.7,zorder=8);ax.annotate('',b,a,arrowprops=dict(arrowstyle='-|>',color=col,lw=1.7),zorder=8)
  if labels:
   off=np.array(labeloffset[cid]);q=a+off;ax.annotate(cid,q,a,color=col,fontsize=13,weight='bold',ha='center',bbox=dict(facecolor='white',edgecolor='none',alpha=.92,pad=2),arrowprops=dict(arrowstyle='-',color=col,lw=.8),zorder=9)
def envelope(ax,v,ids):
 for cid in ids:
  c=specs[cid];o=np.array(records[cid]['world_position_m']);uv=boundary_uv(c);rays=unproject(c,uv)@(R@np.array(c['R_B_optical'])).T;edge=o+.4*rays;pixel=pix(v,np.vstack([edge,edge[0]]));ax.plot(*pixel.T,color=COLORS[cid],lw=1.3,alpha=.92)
  center=np.array([c['optics']['cx_px'],c['optics']['cy_px']])
  for k in ([0,48,96,144] if cid=='C0' else [0,96]):
   # True radial angular arc at the finite display sphere, not a pinhole pyramid.
   rr=unproject(c,center+(uv[k]-center)*np.linspace(0,1,65)[:,None])@(R@np.array(c['R_B_optical'])).T;px=pix(v,o+.4*rr);ax.plot(*px.T,color=COLORS[cid],lw=.75,alpha=.55)
  for k in [0,96]:
   px=pix(v,np.array([o,edge[k]]));ax.plot(*px.T,color=COLORS[cid],lw=.65,alpha=.55)
 axes(ax,v,ids,length=.15,labels=False)
 examples=json.loads((DEBUG/'intersection_examples.json').read_text());pool=[a for a in examples if a['camera_id'] in ids and a['hit_path'].startswith('/World/Person') and .008<a['distance_m']<.35]
 if pool:
  a=min(pool,key=lambda a:a['theta_deg']);origin=np.array(a['origin']);d=np.array(a['direction']);px=pix(v,np.array([origin+max(.002,a['distance_m']-.03)*d,origin+a['distance_m']*d,origin+.4*d]));ax.plot(*px.T,color=COLORS['occlusion'],ls='--',lw=1.5);ax.scatter(*px[1],marker='x',s=35,color=COLORS['occlusion'],zorder=10)
def scene_view(name,bounds):
 ax=fig.add_axes(rect(*bounds));ax.imshow(Image.open(DEBUG/('view_'+name+'_overlap.png')));ax.axis('off')
 # Anchor labels inside the computed category, using its largest inscribed disk.
 from scipy.ndimage import distance_transform_edt
 labels=np.load(DEBUG/('view_'+name+'_overlap.npz'))['labels']
 items=[(5,'三路重叠',(.5,.90))] if name=='B' else [(1,cfg['groups'][name]['ids'][0]+' 单路',(.18,.08)),(4,'两路重叠',(.5,.50)),(2,cfg['groups'][name]['ids'][1]+' 单路',(.82,.08))]
 for category,label,anchor in items:
  mask=labels==category
  if not mask.any():continue
  yy,xx=np.unravel_index(np.argmax(distance_transform_edt(mask)),mask.shape)
  ax.annotate(label,(xx,yy),xytext=anchor,textcoords='axes fraction',ha='center',va='center',fontsize=9,color=INK,bbox=dict(boxstyle='round,pad=.25',facecolor='white',edgecolor='#B4BFCA',alpha=.88,linewidth=.5),arrowprops=dict(arrowstyle='-',color='#C0CED9',linewidth=.8))
 return ax
panels={'A':(80,300,2300,1470),'B':(2420,300,2300,1470),'C':(80,1810,2300,1470),'D':(2420,1810,2300,1470)}
text(80,45,'1.8 m 工厂工人佩戴条件下七相机视场范围示意图',27,weight='bold')
text(80,150,'Step 2.1b-v3  |  绘图基线 956d479 · 无安全帽工人  |  同一工人、同一最终佩戴位姿',15,color=MUTED)
text(80,218,'设备坐标 B：+X 前  ·  +Y 佩戴者左  ·  +Z 上     相机内部布局与光学保持 SIM-V0.2-vfov130',15,color=MUTED)
for k,(x,y,w,h) in panels.items():box(x,y,w,h)
x,y,_,_=panels['A'];text(x+40,y+28,'A  安装关系总览',21,weight='bold');text(x+40,y+103,'完整工人 + 额前组件放大 · 不叠加完整视场包络',14,color=MUTED)
ax,v=capture('body',(x+20,y+185,680,1110));foot=p['floor']['z'];top=foot+1.8;px=pix(v,np.array([[-.30,0,foot],[-.30,0,top]]));ax.annotate('',px[0],px[1],arrowprops=dict(arrowstyle='<->',color=INK,lw=1.5));q=px.mean(0);ax.text(q[0]-45,q[1],'1.800 m\n鞋底—头顶',ha='right',va='center',fontsize=12,color=INK)
ax,v=capture('head',(x+710,y+230,1490,1010));axes(ax,v,list(specs),.055)
# An actual B-frame triad in the head inset.
o=t+R@np.array([.045,-.15,-.08])
for i,label in enumerate(['+X 前','+Y 左','+Z 上']):
 a,b=pix(v,np.array([o,o+R[:,i]*.045]));ax.annotate('',b,a,arrowprops=dict(arrowstyle='-|>',color=INK,lw=1.3));ax.text(*b,label,fontsize=10,color=INK)
text(x+740,y+1260,'前向 C1 / C0 / C2     上视 C3 / C5     下视 C4 / C6',13)
text(x+40,y+1320,'无安全帽工人；鞋底至头顶 1.800 m。设备 scale = 1。',14)
text(x+40,y+1380,f"光心离地：前向 {records['C0']['height_above_floor_m']:.3f} m；上视 {records['C3']['height_above_floor_m']:.3f} m；下视 {records['C4']['height_above_floor_m']:.3f} m。",13,color=MUTED)
for k,name,title,sub in [('B','front','B  前向三目  C1 / C0 / C2','三轴平行 +X；C1—C2 总基线 63 mm；无外撇'),('C','up','C  上视两目  C3 / C5','额前左右上方；两轴 +Z；左右间距 110 mm'),('D','down','D  下视两目  C4 / C6','额前左右下方；两轴 −Z；上下总间距 40 mm')]:
 x,y,_,_=panels[k];text(x+40,y+28,title,21,weight='bold');text(x+40,y+103,sub,14,color=MUTED)
 text(x+40,y+175,'投影生成的轻量边界 · 实体保持可见',12,color=MUTED)
 ax,v=capture(name,(x+20,y+255,1110,1020));envelope(ax,v,cfg['groups'][k]['ids'])
 text(x+1200,y+225,{'B':'C0 实际前向场景图','C':'上视说明图：C3/C5 中点 · 光轴 +Z','D':'下视说明图：C4/C6 中点 · 光轴 −Z'}[k],14,weight='bold')
 scene_view(k,(x+1200,y+360 if k=='B' else y+315,1030,650 if k=='B' else 900))
 if k=='B':
  text(x+1190,y+1110,'C0 画幅内分类；C1/C2 画幅外独占区域不在此图。',12,color=MUTED)
  text(x+40,y+1270,'C0 针孔：1920×1080，120°×130°，独立 fx/fy',13)
  text(x+40,y+1330,'C1/C2 等距：1600×1300，160°×130°；R800 圆 ∩ 画幅',13)
 else:
  text(x+1190,y+1230,'中点参考相机保留 220°投影；未移动真实传感器。',11,color=MUTED)
  text(x+40,y+1280,'等距圆形成像：1080×960；有效直径 960 px；全角 220° / 离轴 110°',13)
  text(x+40,y+1340,'向上 / 顶面方向' if k=='C' else '向下 / 身体前下方与地面方向',13,weight='bold')
 text(x+40,y+1400,'右图轻阴影：场景点近似可见性重叠；左图灰虚线：遮挡影响示意。',11,color=MUTED)
# Global consistent category legend, explicit rather than alpha blending.
legend=[Patch(facecolor='#EDF0F3',edgecolor='#718294',label='单相机覆盖（轻染对应相机色）'),Patch(facecolor='#C8D1DA',label='两路重叠 · 浅蓝灰'),Patch(facecolor='#D0C5D8',label='三路重叠（仅 B）· 浅紫'),Patch(facecolor='#E1E2E3',label='未通过组内可见性检查'),Patch(facecolor='black',label='有效成像圆外')]
fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.015,.125),ncol=5,frameon=False,fontsize=12,handlelength=1.3,columnspacing=1.3)
text(80,3430,'右图：真实场景 RGB + 深度回投影；同一场景点在组内相机中做投影与深度一致性近似检查。',14)
text(80,3495,'阴影表示几何 / 近似可视重叠，不是精确遮挡边界，不等同于完整三维联合覆盖率。场景主体保持可见。',14)
text(80,3560,'左图包络按有限长度显示，不代表相机量程（半径 0.40 m）。VFOV130°与四目圆形220°采用用户确认设置。',13,color=MUTED)
text(80,3625,'不代表深度精度、匹配成功率或 SLAM 结果。C/D 为中点参考视图，真实相机的布局、朝向与光学不变。',13,color=MUTED)
text(80,3690,'本轮无帽人物重新佩戴检查：'+p['fit_status']+'  ·  实际蒙皮与实体网格检查、四向近景复核；详见报告。',13,color=MUTED)
for ext in ['png','pdf','svg']:fig.savefig(OUT/('fov_overview_wearer_v3.'+ext),dpi=200,facecolor='white')
svg=OUT/'fov_overview_wearer_v3.svg';svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
for k,(x,y,w,h) in panels.items():fig.savefig(OUT/'panels'/('panel_'+k+'.png'),dpi=200,bbox_inches=Bbox.from_bounds(x/200,(H-y-h)/200,w/200,h/200),facecolor='white')
plt.close(fig)
for name in ['front','left','right','toprear']:
 im=Image.open(DEBUG/('fit_'+name+'_rgba.png')).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);bg.convert('RGB').save(OUT/('fit_check_'+name+'.png'))
print('SAVED PNG PDF SVG, A/B/C/D panels and four fit views')
