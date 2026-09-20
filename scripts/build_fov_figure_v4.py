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
from overlap_sections_v2 import COLORS
from scene_overlap_v4 import run
run()
OUT=ROOT/'outputs/step2_1b_v4';DEBUG=ROOT/'outputs/step2_1b_v3/debug';REPORT=ROOT/'reports/step2_1b_v4';(OUT/'panels').mkdir(exist_ok=True)
p=json.loads((ROOT/'config/step2_1b_v3/final_placement.json').read_text());cfg=json.loads((ROOT/'config/step2_1b_v4/figure_config.json').read_text());views=json.loads((DEBUG/'external_views.json').read_text());status=json.loads((DEBUG/'render_status.json').read_text());assert status['status']=='PASS'
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
panels={'A':(80,300,2300,1470),'B':(2420,300,2300,1470),'C':(80,1810,2300,1470),'D':(2420,1810,2300,1470)}
text(80,45,'1.8 m 工厂工人佩戴条件下七相机视场范围示意图',27,weight='bold')
text(80,150,'Step 2.1b-v4  |  基于 1186652 · 七路实际相机原图  |  佩戴位姿、外参、FOV 与投影不变',15,color=MUTED)
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

def camera_image(cid,bounds):
 ax=fig.add_axes(rect(*bounds));im=np.asarray(Image.open(OUT/'display'/(cid+'_annotated.png')));h,w=im.shape[:2];ax.imshow(im);data=np.load(OUT/'layers'/(cid+'_classification.npz'));count=data['count'];valid=data['valid'];unknown=data['unknown']
 # Display-only 3 px contour smoothing suppresses dense raster-edge line noise.
 from scipy.ndimage import gaussian_filter
 for n,col in [(2,'#B6D5E4'),(3,'#D5C2E3')]:
  mask=np.ma.array(gaussian_filter((count>=n).astype(float),sigma=3),mask=~valid|unknown)
  if mask.min()<.5<mask.max():ax.contour(mask,levels=[.5],colors=[col],linewidths=.35,alpha=.65)
 if not valid.all():ax.contour(valid.astype(float),levels=[.5],colors=['#A4B0BA'],linewidths=.5,alpha=.7)
 ax.set_xlim(-.5,w-.5);ax.set_ylim(h-.5,-.5);ax.axis('off')
 return ax

for k,name,title,sub in [('B','front','B  前向三目  C1 / C0 / C2','三轴平行 +X；C1/C2 无外撇'),('C','up','C  上视两目  C3 / C5','额前左右上方；两轴 +Z'),('D','down','D  下视两目  C4 / C6','额前左右下方；两轴 −Z')]:
 x,y,_,_=panels[k];text(x+40,y+28,title,21,weight='bold');text(x+40,y+103,sub,14,color=MUTED)
 text(x+40,y+178,'显示该区相关相机的原始图像 · 统一展示增益 +1.5 EV',14,weight='bold')
 if k=='B':
  ax,v=capture(name,(x+35,y+250,380,250));axes(ax,v,cfg['groups'][k],.11,labels=False)
  text(x+470,y+270,'外部示意：仅标光心和短光轴',12,color=MUTED)
  text(x+470,y+340,'下方三张为 C1 / C0 / C2 各自真实输出，完整画幅。',13)
  text(x+470,y+410,'原图层：统一提亮；解释层：浅阴影 + 细边界。',12,color=MUTED)
  for i,cid in enumerate(cfg['groups'][k]):
   xx=x+40+i*755;text(xx,y+535,cid+' 原图',17,weight='bold');camera_image(cid,(xx,y+615,710,580))
  text(x+40,y+1250,'C0：1920×1080 · 针孔 120°×130° · 独立 fx/fy',13)
  text(x+40,y+1315,'C1/C2：1600×1300 · 等距 160°×130° · R800 圆与画幅交集',13)
 else:
  ax,v=capture(name,(x+10,y+470,380,510));axes(ax,v,cfg['groups'][k],.12,labels=False)
  text(x+40,y+1030,'安装方向示意',11,color=MUTED)
  for i,cid in enumerate(cfg['groups'][k]):
   xx=x+430+i*930;text(xx,y+285,cid+' 原图',17,weight='bold');camera_image(cid,(xx,y+375,900,800))
  text(x+430,y+1225,'真实相机完整画幅 · 保留身体、衣物与硬件入镜',12,color=MUTED)
  text(x+40,y+1315,'1080×960 · 220° circular fisheye · 有效直径 960 px · 最大离轴 110°',13)
 text(x+40,y+1400,'解释层只表示组内近似共同可见区域；不以图像明暗判定遮挡。',12,color=MUTED)
legend=[Patch(facecolor='#F6F8FB',edgecolor='#91A0AC',label='单路：保留展示原图'),Patch(facecolor='#C4D8E2',edgecolor='#7396AB',label='两路：轻蓝灰 + 细边界'),Patch(facecolor='#D9CFE1',edgecolor='#A18BAF',label='三路（B）：轻紫 + 细边界'),Patch(facecolor='#F1F3F5',hatch='///',edgecolor='#A5AFB8',label='未知：有效域内无深度'),Patch(facecolor='#191919',edgecolor='#A4B0BA',label='棋盘底：成像有效域外')]
fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.015,.125),ncol=5,frameon=False,fontsize=11,handlelength=1.3,columnspacing=1.25)
text(80,3430,'原图来自 v3 的 C0–C6 实际渲染；七图统一线性 RGB 展示增益 +1.5 EV，未作逐图调色或内容重绘。',14)
text(80,3495,'解释层：同一场景点重投影与深度一致性近似；两路约 10%、三路约 12% 透明着色，细线标出分类边界。',14)
text(80,3560,'鱼眼有效边界保留；域外棋盘与未知斜纹仅属标注层。真实暗色物体保留，黑色不一律代表遮挡。',13,color=MUTED)
text(80,3625,'阴影不是精确遮挡边界、完整三维联合覆盖率、深度精度、匹配成功率或 SLAM 结果。',13,color=MUTED)
text(80,3690,'A 区保持 v3；佩戴位姿、七路外参、FOV 与投影模型未改动。本轮仅调整图面；原始文件与解释层分别保存。',13,color=MUTED)
for ext in ['png','pdf','svg']:fig.savefig(OUT/('fov_overview_wearer_v4.'+ext),dpi=200,facecolor='white')
svg=OUT/'fov_overview_wearer_v4.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
for k,(x,y,w,h) in panels.items():fig.savefig(OUT/'panels'/('panel_'+k+'.png'),dpi=300 if k!='A' else 200,bbox_inches=Bbox.from_bounds(x/200,(H-y-h)/200,w/200,h/200),facecolor='white')
plt.close(fig)
print('SAVED v4 PNG/PDF/SVG and enlarged panels',flush=True)
