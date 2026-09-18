"""Shared nominal geometry. All dimensions in mm unless a field explicitly says m.
New values are simulation assumptions, not recovered/measured hardware parameters.
"""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]

def load_config(path=None):
    return json.loads(Path(path or ROOT/'config/layout_parameters.json').read_text(encoding='utf-8'))

def camera_rotation(forward, up):
    """Columns = optical-frame right, down, forward, expressed in body frame."""
    f=np.asarray(forward,dtype=float); f/=np.linalg.norm(f)
    u=np.asarray(up,dtype=float); u-=f*np.dot(u,f); u/=np.linalg.norm(u)
    r=np.cross(f,u)
    return np.column_stack((r,-u,f))

def quat_wxyz(R):
    q=Rotation.from_matrix(R).as_quat()
    q=q[[3,0,1,2]]
    if q[0]<0: q=-q
    q[np.abs(q)<1e-14]=0
    return q.tolist()

def transform(R,t):
    T=np.eye(4); T[:3,:3]=R; T[:3,3]=t
    return T

def camera_specs(c):
    p=c['layout']; b=p['front_baseline_mm']/2; s=p['surround_baseline_mm']/2
    x=p['surround_x_mm']; z=p['surround_z_half_mm']
    P=Rotation.from_euler('y',p['front_down_pitch_deg'],degrees=True).as_matrix()
    front_f=P@np.array([1.,0,0]); front_u=P@np.array([0.,0,1.])
    specs=[('C0','front_main','前向主相机',[0,0,0],front_f,front_u,'front_main','MCU1'),
           ('C1','front_left','前向左副相机',[0,b,0],front_f,front_u,'front_stereo','MCU1'),
           ('C2','front_right','前向右副相机',[0,-b,0],front_f,front_u,'front_stereo','MCU1'),
           ('C3','surround_left_up','左上环视相机',[x,s,z],[0,0,1],[-1,0,0],'surround','MCU2'),
           ('C4','surround_left_down','左下环视相机',[x,s,-z],[0,0,-1],[1,0,0],'surround','MCU2'),
           ('C5','surround_right_up','右上环视相机',[x,-s,z],[0,0,1],[-1,0,0],'surround','MCU2'),
           ('C6','surround_right_down','右下环视相机',[x,-s,-z],[0,0,-1],[1,0,0],'surround','MCU2')]
    out=[]
    for sid,name,cn,pos,f,u,profile,controller in specs:
        o=c['optics'][profile].copy(); W,H=o['resolution']; cx,cy=W/2,H/2
        if o['model']=='ideal_pinhole':
            focal=W/2/math.tan(math.radians(o['hfov_deg']/2))
            vfov=math.degrees(2*math.atan(H/2/focal))
            maxfov=math.degrees(2*math.atan(math.hypot(W/2,H/2)/focal))
            rad=None
        else:
            maxfov=o['radial_full_fov_deg']
            rad=o.get('image_circle_diameter_px',W)/2
            focal=rad/math.radians(maxfov/2)
            vfov=min(maxfov,math.degrees(H/focal))
        o.update(fx_px=focal,fy_px=focal,cx_px=cx,cy_px=cy,derived_vfov_deg=vfov,
                 radial_full_fov_deg=maxfov,valid_radius_px=rad)
        R=camera_rotation(f,u); U=R@np.diag([1.,-1.,-1.])
        out.append(dict(id=sid,name=name,name_cn=cn,position_mm=list(pos),forward_B=list(map(float,f)),up_B=list(map(float,u)),
                        R_B_optical=R.tolist(),R_B_usd=U.tolist(),q_B_optical_wxyz=quat_wxyz(R),q_B_usd_wxyz=quat_wxyz(U),
                        optics=o,controller=controller,prim_path=f'/SevenCameraRig/Sensors/{sid}_{name}'))
    return out

def geometry_specs(c):
    p=c['layout']; g=c['geometry']; out=[]
    def box(name,group,dat): out.append(dict(name=name,group=group,kind='box',**dat))
    box('central_housing','Housing',g['central_housing'])
    for name,sgn in [('left_pod',1),('right_pod',-1)]:
        box(name,'Housing',dict(center_mm=[p['surround_x_mm'],sgn*p['surround_baseline_mm']/2,0],size_mm=g['side_pod_size_mm']))
    for cam in camera_specs(c):
        b=g['front_barrel' if cam['id'] in ('C0','C1','C2') else 'surround_barrel']
        d=np.array(cam['forward_B']); pos=np.array(cam['position_mm'])
        a=pos-d*b['back_start_mm']; e=pos-d*b['back_end_mm']
        out.append(dict(name=cam['id']+'_barrel',group='Housing',kind='cylinder',a_mm=a.tolist(),b_mm=e.tolist(),radius_mm=b['radius_mm']))
    box('right_heatsink','Accessories',g['right_heatsink'])
    for key in ('strap_left','strap_right','strap_rear','strap_left_bracket'): box(key,'WearerMount',g[key])
    points=g['usb_cable']['points_mm']
    for i,(a,b) in enumerate(zip(points[:-1],points[1:])):
        out.append(dict(name=f'usb_cable_{i}',group='Accessories',kind='cylinder',a_mm=a,b_mm=b,radius_mm=g['usb_cable']['radius_mm']))
    h=g['head_proxy']
    out.append(dict(name='head_ellipsoid',group='Wearer',kind='ellipsoid',center_mm=h['center_mm'],radii_mm=(np.array(h['radii_mm'])*h['scale']).tolist()))
    return out

def pixel_rays(cam, stride=1):
    """Pinhole/equidistant exact nominal unit rays; u/v refer to pixel-center coordinates."""
    o=cam['optics']; W,H=o['resolution']
    us=np.arange(0,W,stride,dtype=float)+.5; vs=np.arange(0,H,stride,dtype=float)+.5
    U,V=np.meshgrid(us,vs); X=U-o['cx_px']; Y=V-o['cy_px']
    rad=np.hypot(X,Y)
    if o['model']=='ideal_pinhole':
        r=np.stack([X/o['fx_px'],Y/o['fy_px'],np.ones_like(X)],axis=-1)
        r/=np.linalg.norm(r,axis=-1,keepdims=True); valid=np.ones_like(X,dtype=bool)
    else:
        theta=rad/o['fx_px']; k=np.divide(np.sin(theta),rad,out=np.full_like(rad,1/o['fx_px']),where=rad>1e-12)
        r=np.stack([X*k,Y*k,np.cos(theta)],axis=-1)
        valid=theta<=math.radians(o['radial_full_fov_deg']/2)+1e-12
    return r@np.asarray(cam['R_B_optical']).T,valid

def nearest_hit(origin, rays, obj):
    """Analytic ray/proxy intersections (positive distances, mm)."""
    O=np.asarray(origin,float); D=np.asarray(rays,float); eps=1e-8
    if obj['kind']=='box':
        lo=np.array(obj['center_mm'])-np.array(obj['size_mm'])/2
        hi=np.array(obj['center_mm'])+np.array(obj['size_mm'])/2
        parallel=np.abs(D)<1e-14
        inv=np.divide(1.,D,out=np.zeros_like(D),where=~parallel)
        t1=(lo-O)*inv; t2=(hi-O)*inv
        near=np.minimum(t1,t2); far=np.maximum(t1,t2)
        near=np.where(parallel,-np.inf,near); far=np.where(parallel,np.inf,far)
        invalid=np.any(parallel & ((O<lo)|(O>hi)),axis=-1)
        tmin=near.max(axis=-1); tmax=far.min(axis=-1)
        hit=np.where(tmin>eps,tmin,tmax)
        return np.where((~invalid)&(tmax>=np.maximum(tmin,eps)),hit,np.inf)
    if obj['kind']=='ellipsoid':
        r=np.array(obj['radii_mm']); o=(O-np.array(obj['center_mm']))/r; d=D/r
        a=(d*d).sum(axis=-1); b=2*(d*o).sum(axis=-1); cc=np.dot(o,o)-1
        disc=b*b-4*a*cc; sq=np.sqrt(np.maximum(disc,0)); t1=(-b-sq)/(2*a);t2=(-b+sq)/(2*a)
        return np.where((disc>=0)&(t2>eps),np.where(t1>eps,t1,t2),np.inf)
    if obj['kind']=='cylinder':
        a=np.array(obj['a_mm'],float); b=np.array(obj['b_mm'],float); v=b-a; L=np.linalg.norm(v);v/=L
        w=O-a; dz=D@v; wz=w@v; dp=D-dz[...,None]*v; wp=w-wz*v
        aa=(dp*dp).sum(axis=-1); bb=2*(dp*wp).sum(axis=-1); cc=wp@wp-obj['radius_mm']**2
        disc=bb*bb-4*aa*cc; safe=np.where(aa>1e-15,aa,1)
        root=np.sqrt(np.maximum(disc,0)); best=np.full(D.shape[:-1],np.inf)
        for sign in (-1,1):
            t=(-bb+sign*root)/(2*safe); z=wz+t*dz
            ok=(aa>1e-15)&(disc>=0)&(t>eps)&(z>=0)&(z<=L)
            best=np.minimum(best,np.where(ok,t,np.inf))
        for h in (0.,L):
            t=np.divide(h-wz,dz,out=np.full_like(dz,np.inf),where=np.abs(dz)>1e-14)
            radial=wp+t[...,None]*dp
            ok=(np.isfinite(t))&(t>eps)&((radial*radial).sum(axis=-1)<=obj['radius_mm']**2)
            best=np.minimum(best,np.where(ok,t,np.inf))
        return best
    raise ValueError(obj['kind'])
