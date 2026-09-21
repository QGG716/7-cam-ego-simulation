"""Continuous edge coordinates: pixel (row,col) has center (col+.5,row+.5)."""
import numpy as np


def unproject(cam, uv):
    o = cam['optics']
    xy = np.asarray(uv, dtype=float) - [o['cx_px'], o['cy_px']]
    if o['model'] == 'ideal_pinhole':
        rays = np.concatenate((xy / [o['fx_px'], o['fy_px']], np.ones(xy.shape[:-1] + (1,))), axis=-1)
        return rays / np.linalg.norm(rays, axis=-1, keepdims=True)
    normalized = xy / [o['fx_px'], o['fy_px']]
    t = np.linalg.norm(normalized, axis=-1)
    k = np.divide(np.sin(t), t, out=np.ones_like(t), where=t>1e-14)
    return np.concatenate((normalized*k[...,None], np.cos(t)[...,None]), axis=-1)


def project(cam, rays):
    o = cam['optics']
    d = np.asarray(rays, dtype=float)
    rho = np.linalg.norm(d[...,:2], axis=-1)
    if o['model'] == 'ideal_pinhole':
        xy = d[...,:2] / d[...,2,None] * [o['fx_px'], o['fy_px']]
        angular = d[...,2] > 0
    else:
        theta = np.arctan2(rho, d[...,2])
        k = np.divide(theta, rho, out=np.zeros_like(rho), where=rho>1e-14)
        xy = d[...,:2]*k[...,None]*[o['fx_px'], o['fy_px']]
        angular = theta <= np.deg2rad(o['radial_full_fov_deg']/2) + 1e-12
    uv = xy + [o['cx_px'], o['cy_px']]
    w,h = o['resolution']
    valid = angular & (uv[...,0]>=0) & (uv[...,0]<=w) & (uv[...,1]>=0) & (uv[...,1]<=h)
    return uv, valid


def angle_targets(cam):
    targets = []
    if cam['id'] in ('C0','C1'):
        horizontal = (59,61) if cam['id']=='C0' else (79,81)
        for axis, angles in [('horizontal',horizontal),('vertical',(64,66))]:
            for angle in angles:
                for sign in (-1,1):
                    a = np.deg2rad(angle*sign)
                    ray = [np.sin(a),0,np.cos(a)] if axis=='horizontal' else [0,np.sin(a),np.cos(a)]
                    targets.append(dict(name=f'{axis}_{sign*angle:+d}', angle_deg=sign*angle, azimuth_deg=0 if axis=='horizontal' else 90, ray=ray))
    else:
        for angle,az in [(0,0),(60,0),(95,0),(105,0),(115,0),(105,135)]:
            a,p = np.deg2rad([angle,az])
            targets.append(dict(name=f'theta{angle}_az{az}',angle_deg=angle,azimuth_deg=az,
                                ray=[np.sin(a)*np.cos(p),np.sin(a)*np.sin(p),np.cos(a)]))
    for t in targets:
        uv, valid = project(cam,t['ray'])
        t.update(theoretical_uv_px=uv.tolist(),theoretical_visible=bool(valid),distance_m=1.,radius_m=.006)
    return targets
