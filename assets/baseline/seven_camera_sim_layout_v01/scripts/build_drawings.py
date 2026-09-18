#!/usr/bin/env python3
"""A3 vector layout sheets and millimeter DXF, generated from layout_parameters.json.
This is a simulation datum/occlusion model drawing, not a manufacturing drawing.
"""
from __future__ import annotations
import itertools, math
import numpy as np
from scipy.spatial import ConvexHull
import ezdxf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,Color,white
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT,TA_CENTER
from xml.sax.saxutils import escape
from rig_common import ROOT,load_config,camera_specs,geometry_specs

CN='/usr/share/fonts/truetype/arphic/uming.ttc'
pdfmetrics.registerFont(TTFont('CN',CN,subfontIndex=0))
pdfmetrics.registerFont(TTFont('Mono','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'))
W,H=landscape(A3)
INK=HexColor('#193344'); GRAY=HexColor('#64717a'); LIGHT=HexColor('#edf3f6'); LINE=HexColor('#bcc8d0'); ACCENT=HexColor('#256287')
FRONT=np.array([[0,-1,0],[0,0,1.]])
TOP=np.array([[0,-1,0],[1,0,0.]])
RIGHT=np.array([[1,0,0],[0,0,1.]])


def txt(c,x,y,s,size=11,color=INK,font='CN',align='left'):
    c.setFillColor(color);c.setFont(font,size)
    if align=='center':c.drawCentredString(x,y,s)
    elif align=='right':c.drawRightString(x,y,s)
    else:c.drawString(x,y,s)

def para(c,x,y,w,s,size=11,leading=None,color=INK):
    style=ParagraphStyle('p',fontName='CN',fontSize=size,leading=leading or size*1.55,textColor=color,wordWrap='CJK')
    p=Paragraph(escape(s).replace('\n','<br/>'),style); ww,hh=p.wrap(w,900);p.drawOn(c,x,y-hh);return y-hh

def line(c,a,b,color=INK,width=.7,dash=None):
    c.setStrokeColor(color);c.setLineWidth(width);c.setDash(dash or []);c.line(*a,*b);c.setDash([])

def poly(c,pts,color=INK,width=.65,fill=None):
    p=c.beginPath();p.moveTo(*pts[0]);[p.lineTo(*pt) for pt in pts[1:]];p.close()
    c.setStrokeColor(color);c.setLineWidth(width)
    if fill:c.setFillColor(fill)
    c.drawPath(p,stroke=1,fill=bool(fill))

def arrow(c,a,b,color=ACCENT,width=1.1,head=6):
    a=np.array(a,float);b=np.array(b,float);line(c,a,b,color,width)
    d=b-a;norm=np.linalg.norm(d)
    if norm<1e-9:return
    d/=norm;n=np.array([-d[1],d[0]])
    poly(c,[b,b-head*d+head*.36*n,b-head*d-head*.36*n],color,width,fill=color)

def cross(c,x,y,r=5,color=ACCENT):
    line(c,(x-r,y),(x+r,y),color,.85);line(c,(x,y-r),(x,y+r),color,.85)
    c.setStrokeColor(color);c.setLineWidth(.85);c.circle(x,y,r*.52,fill=0)

def project(g,P):
    if g['kind']=='box':
        cen=np.array(g['center_mm']);half=np.array(g['size_mm'])/2
        v=np.array([cen+half*np.array(s) for s in itertools.product((-1,1),repeat=3)])
    elif g['kind']=='cylinder':
        a=np.array(g['a_mm'],dtype=float);b=np.array(g['b_mm'],dtype=float);d=b-a;d/=np.linalg.norm(d)
        u=np.cross(d,[1,0,0])
        if np.linalg.norm(u)<.01:u=np.cross(d,[0,1,0])
        u/=np.linalg.norm(u);v0=np.cross(d,u)
        v=np.array([p+g['radius_mm']*(math.cos(t)*u+math.sin(t)*v0) for p in (a,b) for t in np.linspace(0,2*math.pi,65)[:-1]])
    else:
        cen=P@np.array(g['center_mm']);S=P@np.diag(np.array(g['radii_mm'])**2)@P.T
        vals,vecs=np.linalg.eigh(S)
        return np.array([cen+vecs@np.diag(np.sqrt(vals))@np.array([math.cos(t),math.sin(t)]) for t in np.linspace(0,2*math.pi,81)])
    q=v@P.T; uniq=np.unique(np.round(q,8),axis=0)
    return uniq[ConvexHull(uniq).vertices]

def view(c,geo,P,origin,scale,groups=None):
    origin=np.array(origin)
    order={'Wearer':0,'WearerMount':1,'Accessories':2,'Housing':3}
    for g in sorted(geo,key=lambda a:order[a['group']]):
        if groups and g['group'] not in groups:continue
        q=project(g,P)*scale+origin
        fc=Color(.975,.98,.985) if g['group']=='Housing' else Color(.93,.94,.95)
        poly(c,q,GRAY if g['group'] in ('Wearer','WearerMount') else INK,.75,fc)

def dimh(c,x1,x2,object_y,dim_y,label,size=10):
    if x2<x1:x1,x2=x2,x1
    for x in (x1,x2):line(c,(x,object_y),(x,dim_y+(-4 if dim_y<object_y else 4)),GRAY,.4)
    line(c,(x1,dim_y),(x2,dim_y),INK,.65)
    for x,sgn in ((x1,1),(x2,-1)):
        poly(c,[(x,dim_y),(x+sgn*5,dim_y+1.6),(x+sgn*5,dim_y-1.6)],INK,.5,INK)
    txt(c,(x1+x2)/2,dim_y+5,label,size,align='center')

def dimv(c,y1,y2,object_x,dim_x,label,size=10):
    if y2<y1:y1,y2=y2,y1
    for y in (y1,y2):line(c,(object_x,y),(dim_x+(-4 if dim_x<object_x else 4),y),GRAY,.4)
    line(c,(dim_x,y1),(dim_x,y2),INK,.65)
    for y,sgn in ((y1,1),(y2,-1)):
        poly(c,[(dim_x,y),(dim_x+1.6,y+sgn*5),(dim_x-1.6,y+sgn*5)],INK,.5,INK)
    c.saveState();c.translate(dim_x+7,(y1+y2)/2);c.rotate(90);txt(c,0,0,label,size,align='center');c.restoreState()

def datum(c,p,label,dx=10,dy=12):
    cross(c,*p);q=np.array(p)+[dx,dy];line(c,p,q,ACCENT,.55)
    txt(c,q[0]+(2 if dx>=0 else -2),q[1],label,10,ACCENT,align='left' if dx>=0 else 'right')

def frame(c,num,title):
    c.setFillColor(white);c.rect(0,0,W,H,fill=1,stroke=0)
    c.setStrokeColor(INK);c.setLineWidth(.8);c.rect(24,24,W-48,H-48,fill=0)
    c.setFillColor(LIGHT);c.rect(25,H-93,W-50,68,fill=1,stroke=0)
    txt(c,43,H-59,'七目相机与 IMU｜'+title,23)
    txt(c,44,H-82,'仿真结构布置基线  SIM-V0.1  ·  2026-09-18',11,GRAY)
    txt(c,W-43,H-60,'A3 / 毫米',12,align='right')
    txt(c,W-43,H-82,'非加工图 · 非实测标定',11,GRAY,align='right')
    line(c,(24,70),(W-24,70),INK,.8)
    txt(c,40,50,'来源标记：D＝客户PDF；S＝组成图；A＝本版仿真假设。除明确D项外，尺寸均为A。',10)
    txt(c,40,34,'工程文件以 config/layout_parameters.json 为唯一参数源；CAD用mm，USD/外参矩阵用m；视图不按比例量取。',9,GRAY)
    txt(c,W-40,45,f'SC7-SIM-0{num}   |   {num} / 4',11,font='Mono',align='right')

def header(c,x,y,title):
    txt(c,x,y,title,14);line(c,(x,y-7),(x+300,y-7),LINE,.8)

def table(c,x,top,widths,rows,size=11,rowh=None):
    st=ParagraphStyle('t',fontName='CN',fontSize=size,leading=size*1.4,wordWrap='CJK',textColor=INK)
    data=[[Paragraph(escape(str(v)).replace('\n','<br/>'),st) for v in row] for row in rows]
    t=Table(data,colWidths=widths,rowHeights=rowh,repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9)]))
    tw,th=t.wrap(1100,900);t.drawOn(c,x,top-th);return top-th

def main():
    C=load_config();cams=camera_specs(C);geo=geometry_specs(C);out=ROOT/'drawings';out.mkdir(exist_ok=True)
    c=canvas.Canvas(str(out/'七目相机IMU_仿真结构布局_SIM-V0.1.pdf'),pagesize=(W,H))
    c.setTitle('七目相机IMU仿真结构布局 SIM-V0.1');c.setAuthor('Simulation engineering layout')
    core=[g for g in geo if not g['name'].startswith('usb_cable')]
    # SHEET 1: sensor-rig datum layout
    frame(c,1,'光心定位与三视图')
    header(c,52,726,'正视图｜从前方沿 -X 看向佩戴者')
    origin=np.array([321.,594.]);s=3.25
    view(c,core,FRONT,origin,s,{'Housing','Accessories'})
    line(c,(85,594),(634,594),LINE,.55,[5,3]);line(c,(321,487),(321,685),LINE,.55,[5,3])
    offsets={'C0':(0,-39),'C1':(-7,-30),'C2':(7,-30),'C3':(-12,15),'C4':(-12,-20),'C5':(12,15),'C6':(12,-20)}
    for cam in cams:
        pos=origin+s*(FRONT@cam['position_mm']);dx,dy=offsets[cam['id']];datum(c,pos,cam['id'],dx,dy)
        if cam['id'] in ('C3','C4','C5','C6'):
            d=FRONT@cam['forward_B'];arrow(c,pos+d*7,pos+d*30)
    dimh(c,321-31.5*s,321+31.5*s,583,481,'63  [D]')
    dimh(c,321-55*s,321+55*s,659,693,'110  [A]')
    txt(c,92,467,'图上左侧＝佩戴者左侧；本页省略长线束，见第3页。',10,GRAY)
    header(c,52,419,'俯视图｜+X向前（图上方），+Y向左')
    org=np.array([321.,331.]);view(c,core,TOP,org,s,{'Housing','Accessories'})
    line(c,(org[0],173),(org[0],391),LINE,.55,[5,3])
    for cam in cams[:3]:
        pos=org+s*(TOP@cam['position_mm']);datum(c,pos,cam['id'],0,20);arrow(c,pos+[0,6],pos+[0,38])
    for sid in ('C3','C5'):
        cam=next(a for a in cams if a['id']==sid);pos=org+s*(TOP@cam['position_mm'])
        datum(c,pos,'C3/C4' if sid=='C3' else 'C5/C6',-15 if sid=='C3' else 15,0)
    ip=org+s*(TOP@C['layout']['imu_position_mm']);datum(c,ip,'I0',-30,-23)
    dimv(c,331-16*s,331,321+55*s,636,'16  [A]')
    dimv(c,331-18*s,331,321,393,'18  [A]')
    para(c,53,145,608,'上、下相机光心具有相同X/Y坐标，分别位于Z=+20/-20 mm；不是同一个光心。\n镜头圆柱仅表示镜筒后部。所有光心均位于不透明结构之外。',10.5)
    line(c,(690,104),(690,731),LINE,.8)
    header(c,724,726,'右视图｜从佩戴者右侧沿 +Y 观察')
    org=np.array([957.,596.]);view(c,core,RIGHT,org,s,{'Housing','Accessories'})
    for sid,lab,dx,dy in [('C0','C0/C1/C2',12,8),('C5','C3/C5',-5,17),('C6','C4/C6',-5,-21)]:
        cam=next(a for a in cams if a['id']==sid);pos=org+s*(RIGHT@cam['position_mm']);datum(c,pos,lab,dx,dy)
        d=RIGHT@cam['forward_B'];arrow(c,pos+d*8,pos+d*34)
    ip=org+s*(RIGHT@C['layout']['imu_position_mm']);datum(c,ip,'I0',-49,4)
    dimv(c,596-20*s,596+20*s,957-16*s,1035,'40  [A]')
    header(c,724,448,'本版固定的仿真坐标')
    y=424
    for t in ['原点O_B：C0主相机名义光心。','+X：设备正前方；+Y：佩戴者左方；+Z：上方。','前向三目：光轴 +X；上方两目：+Z；下方两目：-Z。','IMU：(-18, 0, 0) mm，三轴与机体坐标一致。','上述方向、110/40/16/18 mm尺寸均为建模假设；来源图没有提供这些测量值。']:
        y=para(c,726,y,399,t,11)-10
    y=para(c,726,y-4,398,'63 mm和中点关系来自客户PDF第2页§3。此处将“相机中心”解释为仿真投影中心；实物镜筒中心与光心的偏移仍待供应商确认。',10.5,color=GRAY)
    c.showPage()
    # SHEET 2: explicit transformations
    frame(c,2,'相机—IMU外参定义')
    txt(c,47,725,'表中位置均相对于O_B；光轴/图像上方向量用于唯一确定朝向（含滚转角）。',12)
    rows=[['编号','传感器','X / mm','Y / mm','Z / mm','光轴方向（B）','图像上方（B）','位置与朝向依据']]
    for cam in cams:
        axis='+X' if cam['id'] in ('C0','C1','C2') else ('+Z' if cam['id'] in ('C3','C5') else '-Z')
        up='+Z' if cam['id'] in ('C0','C1','C2') else ('-X' if cam['id'] in ('C3','C5') else '+X')
        rows.append([cam['id'],cam['name_cn'],*[f'{v:g}' for v in cam['position_mm']],axis,up,'D：63 mm / 中点；A：朝向' if cam['id'] in ('C0','C1','C2') else 'A：本版仿真假设'])
    rows.append(['I0','IMU','-18','0','0','不适用','不适用','A：位置；IMU三轴与B平行'])
    end=table(c,46,706,[48,148,75,75,75,139,139,345],rows,11,rowh=35)
    header(c,47,350,'相机光学坐标：x向右，y向下，z沿光轴')
    txt(c,47,321,'R_B_C 的三列＝相机 x / y / z 轴在B中的方向。以下矩阵为本版名义姿态：',11)
    mats=[('C0 / C1 / C2',np.array(cams[0]['R_B_optical'])),('C3 / C5',np.array(cams[3]['R_B_optical'])),('C4 / C6',np.array(cams[4]['R_B_optical']))]
    for (title,R),x in zip(mats,[62,426,790]):
        txt(c,x,289,title,13,font='Mono')
        for i,row in enumerate(R):txt(c,x,264-21*i,'[ '+'  '.join(f'{int(v):2d}' for v in row)+' ]',13,font='Mono')
    txt(c,49,182,'p_B = R_B_C p_C + t_B_C',15,font='Mono')
    txt(c,49,157,'T_C_I = inverse(T_B_C) T_B_I',13,font='Mono')
    para(c,433,185,704,'JSON/YAML已给出双向4×4外参：T_B_C、T_C_B、T_I_C、T_C_I。平移以米存储，采用列向量变换；数组按行列出。四元数明确使用w,x,y,z顺序。',11)
    para(c,49,123,1082,'USD相机采用+Y向上、-Z向前，不能把光学坐标系旋转直接填入USD。已单独导出 q_B_usd_wxyz，且 R_B_USD = R_B_C × diag(1,-1,-1)。IMU外参是布置设计值，不是出厂标定值。',10.5,color=GRAY)
    c.showPage()
    # SHEET 3: occluder proxies
    frame(c,3,'外壳与佩戴遮挡占位')
    header(c,49,725,'俯视占位｜装置、头带、线束和头部')
    origin=np.array([319.,672.]);s2=1.58
    view(c,geo,TOP,origin,s2)
    for sid in ('C0','C1','C2','C3','C5'):
        cam=next(a for a in cams if a['id']==sid);pos=origin+s2*(TOP@cam['position_mm'])
        if sid=='C0':datum(c,pos,'O_B / C0',0,23)
        elif sid=='C3':datum(c,pos,'C3/C4',-25,0)
        elif sid=='C5':datum(c,pos,'C5/C6',34,-6)
    datum(c,origin+s2*(TOP@[-120,0,-25]),'头部占位中心',-18,15)
    dimv(c,672-120*s2,672,319,505,'120  [A]')
    dimh(c,319-72*s2,319+72*s2,672-120*s2,305,'头部宽144  [A]')
    txt(c,78,289,'U形头带为矩形截面占位，未模拟弹性、贴合和头围调节。',10,GRAY)
    header(c,640,725,'侧视占位｜前端相机不能穿入头部模型')
    origin=np.array([1058.,548.]);view(c,geo,RIGHT,origin,s2)
    for sid,lab,dx,dy in [('C0','O_B/C0',11,5),('C5','C3/C5',5,20),('C6','C4/C6',5,-26)]:
        cam=next(a for a in cams if a['id']==sid);pos=origin+s2*(RIGHT@cam['position_mm']);datum(c,pos,lab,dx,dy)
        d=RIGHT@cam['forward_B'];arrow(c,pos+d*6,pos+d*35)
    dimh(c,1058-205*s2,1058-35*s2,548-25*s2,694,'头部长170  [A]')
    dimv(c,548-130*s2,548+80*s2,1058-120*s2,681,'头部高210  [A]')
    txt(c,762,287,'头部中心(-120,0,-25)，半轴(85,72,105) mm。',10,GRAY)
    cols=[(48,347,'Housing｜设备本体','中央壳体：26×86×26 mm。\n侧壳体：每侧28×24×28 mm。\n镜筒：前向半径6 mm、环视半径6 mm；仅保留后部不透明外形。'),
          (424,344,'Accessories｜附件','散热块：32×17×24 mm；置于右侧。\nUSB线束：半径2.5 mm，后向折线占位。\n体积和走线均非厂家图纸，不用于散热或强度结论。'),
          (799,343,'Wearer / WearerMount｜佩戴体','头部是可调椭球，不代表人体标准。\n本版不含鼻、耳、头发、颈部、肩膀和手臂；人体遮挡结论只适用于该简化模型。')]
    for x,w,title,text in cols:
        c.setFillColor(LIGHT);c.rect(x,97,w,153,fill=1,stroke=0)
        txt(c,x+12,228,title,13);para(c,x+12,212,w-24,text,10.8)
    c.showPage()
    # SHEET 4: projection and handover
    frame(c,4,'光学假设与Isaac交接')
    rows=[['对象','名义分辨率 / 帧率','采用的投影假设','名义f / 主点（px）','有效区域与来源边界']]
    for cam,label in [(cams[0],'C0 主相机'),(cams[1],'C1/C2 副相机'),(cams[3],'C3—C6 环视')]:
        o=cam['optics'];ww,hh=o['resolution']
        m='理想针孔；HFOV 120 deg [D]' if cam['id']=='C0' else ('理想等距；HFOV 160 deg [D]' if cam['id']=='C1' else '理想等距；圆形成像全角220 deg [S+A]')
        bound='矩形全幅；垂直视场约%.2f deg为假设模型的计算值。'%o['derived_vfov_deg'] if cam['id']=='C0' else ('半径800 px圆形边界与1600×1300画幅相交；区域边界为A。' if cam['id']=='C1' else '1080×960画幅内设直径960 px成像圆；220 deg的圆形解释与成像圆尺寸均为A。')
        rows.append([label,f'{ww}×{hh} / 30 FPS',m,f'{o["fx_px"]:.6f}\n({o["cx_px"]:g}, {o["cy_px"]:g})',bound])
    y=table(c,45,726,[110,180,252,176,376],rows,10.8,rowh=[34,65,65,65])
    para(c,47,y-15,1100,'说明：PDF并未给出真实镜头模型、VFOV、有效成像圆、畸变系数和IMU安装位置。本页是仿真输入，不是替代客户指标。PDF中左右副相机分辨率下限为1600×1300；本版两路均取此值。图中右副相机1630和“IMUx1000”保留为待确认信息；仿真IMU默认200 Hz，不擅自提升客户要求。',11)
    header(c,48,397,'Isaac导入后按三层验证')
    y=373
    for title,body in [
        ('1 / 布局与遮挡','切换ideal、body、worn三种可见层：仅镜头模型；本体/附件；本体/附件/佩戴占位。分别检查单目遮挡、七目覆盖与重叠，而不是把理想FOV直接当成有效覆盖。'),
        ('2 / 渲染与射线','鱼眼不能用普通针孔角度替代。先在无占位遮挡条件下检查0、60、95、105 deg目标：220 deg模型应保留超过90 deg的光线。近裁剪面为0.1 mm，防止近场结构被误裁掉。'),
        ('3 / 运动、IMU与SLAM','本包提供传感器布局和IMU安装坐标，未生成真实IMU时序、运动轨迹或SLAM结果。后续接入连续六自由度轨迹、纹理场景与同步采集；仿真真值只作评价，不输入SLAM求解。')]:
        txt(c,51,y,title,12); y=para(c,51,y-12,667,body,10.8)-17
    c.setFillColor(LIGHT);c.rect(756,100,386,292,fill=1,stroke=0)
    txt(c,772,371,'文件与验证状态',14)
    yy=350
    for body in [
        'STEP：可编辑几何装配；零件有独立名称，尺寸单位mm。',
        'USDA：七个Camera prim与IMU安装坐标，单位m；为RTX鱼眼写入兼容投影属性。',
        'JSON/YAML/CSV/URDF：相同参数源派生的名义外参和TF。',
        '已做：STEP回读、几何有效性和外参数学自检。',
        '未做：本机没有Isaac RTX运行环境；USD运行时解析、鱼眼渲染与SLAM验收须在目标机完成。'
    ]:yy=para(c,772,yy,354,body,10.3)-10
    txt(c,48,91,'客户依据：PDF第2页§3、第4页§6.2/6.4、第6页§9、第7页§11；Isaac官方接口说明见README。',9,GRAY)
    c.save()
    # DXF: coordinates in millimeters, orthographic views translated on a layout canvas.
    d=ezdxf.new('R2018');d.units=4
    for layer,col in [('HOUSING',7),('ACCESSORIES',8),('WEARER',9),('DATUM',4),('DIM',2),('NOTES',7)]:d.layers.new(layer,dxfattribs={'color':col})
    ms=d.modelspace()
    def add_text(t,p,h=3,layer='NOTES'):ms.add_text(t,dxfattribs={'height':h,'layer':layer}).set_placement(p)
    def dxfview(P,origin,groups,name):
        O=np.array(origin)
        for g in geo:
            if g['group'] not in groups:continue
            if 'Wearer' not in groups and g['name'].startswith('usb_cable'):continue
            pts=project(g,P)+O;lay='HOUSING' if g['group']=='Housing' else ('ACCESSORIES' if g['group']=='Accessories' else 'WEARER')
            ms.add_lwpolyline(pts.tolist(),close=True,dxfattribs={'layer':lay})
        for cam in cams:
            p=O+P@cam['position_mm'];ms.add_circle(p,1,dxfattribs={'layer':'DATUM'});ms.add_line(p+[-2,0],p+[2,0],dxfattribs={'layer':'DATUM'});ms.add_line(p+[0,-2],p+[0,2],dxfattribs={'layer':'DATUM'})
        ip=O+P@C['layout']['imu_position_mm'];ms.add_circle(ip,1.8,dxfattribs={'layer':'DATUM'})
        add_text(name,O+[-75,45],4)
    dxfview(FRONT,[100,360],{'Housing','Accessories'},'FRONT: LOOK -X; WEARER LEFT AT LEFT')
    dxfview(TOP,[100,215],{'Housing','Accessories'},'TOP: +X UP')
    dxfview(RIGHT,[350,360],{'Housing','Accessories'},'RIGHT: LOOK +Y')
    for a,b,y,text in [([68.5,360],[131.5,360],325,'63 [PDF]'),([45,380],[155,380],410,'110 [ASSUMED]')]:
        dim=ms.add_linear_dim(base=(0,y),p1=a,p2=b,angle=0,text=text,dimstyle='EZDXF',dxfattribs={'layer':'DIM'});dim.render()
    dim=ms.add_linear_dim(base=(385,0),p1=(334,340),p2=(334,380),angle=90,text='40 [ASSUMED]',dimstyle='EZDXF',dxfattribs={'layer':'DIM'});dim.render()
    dxfview(TOP,[600,355],{'Housing','Accessories','WearerMount','Wearer'},'WORN TOP: ALL PROXIES ASSUMED')
    dxfview(RIGHT,[1020,270],{'Housing','Accessories','WearerMount','Wearer'},'WORN RIGHT')
    add_text('SC7-SIM-V0.1 | mm | SIMULATION DATUM LAYOUT - NOT A MANUFACTURING DRAWING',[20,465],6)
    add_text('ORIGIN = C0 OPTICAL CENTER; +X FORWARD, +Y WEARER LEFT, +Z UP. EXCEPT 63 mm / MIDPOINT, DIMENSIONS ARE ASSUMPTIONS.',[20,451],3)
    for i,cam in enumerate(cams):
        pos=' '.join(f'{v:g}' for v in cam['position_mm']);add_text(f'{cam["id"]} {cam["name"]}: ({pos}) mm',[250,210-i*8],3)
    add_text('I0 IMU: (-18 0 0) mm; axes aligned with body; proposed, not measured.',[250,146],3)
    add_text('STEP/DXF mm; USD/extrinsic translations m. No holes, tolerances, mass or lens calibration specified.',[20,80],3)
    d.saveas(out/'seven_camera_layout_mm.dxf')
    print('Created A3 four-sheet PDF and millimeter DXF')

if __name__=='__main__':main()
