#!/usr/bin/env python3
"""Generate CAD, USD and machine-readable extrinsics from one parameter file.
Run with ordinary Python + cadquery + scipy + numpy + PyYAML. No Isaac required.
USD is authored as ASCII; validate it in the installed Isaac/pxr environment.
"""
from __future__ import annotations
import argparse, csv, json, math
from pathlib import Path
import numpy as np
import yaml
import cadquery as cq
from scipy.spatial.transform import Rotation
from rig_common import ROOT,load_config,camera_specs,geometry_specs,quat_wxyz,transform

COLORS={'Housing':(.24,.28,.33),'Accessories':(.50,.53,.57),'WearerMount':(.16,.17,.19),'Wearer':(.67,.61,.53)}

def shape_for(g):
    if g['kind']=='box':
        return cq.Workplane('XY').box(*g['size_mm']).translate(g['center_mm']).val()
    if g['kind']=='cylinder':
        a=np.array(g['a_mm']);v=np.array(g['b_mm'])-a
        return cq.Solid.makeCylinder(g['radius_mm'],float(np.linalg.norm(v)),cq.Vector(*a),cq.Vector(*v))
    if g['kind']=='ellipsoid':
        r=g['radii_mm']; c=g['center_mm']
        mat=cq.Matrix([[r[0],0,0,c[0]],[0,r[1],0,c[1]],[0,0,r[2],c[2]],[0,0,0,1]])
        return cq.Workplane('XY').sphere(1).val().transformGeometry(mat)
    raise ValueError(g['kind'])

def fmtv(v): return '('+', '.join(f'{float(x):.12g}' for x in v)+')'

def usd_mesh(name, shape, color, indent=8):
    verts,tris=shape.tessellate(0.35,0.20)
    pts=[np.array(v.toTuple())*.001 for v in verts]
    pad=' '*indent; p2=pad+'    '
    counts=', '.join(['3']*len(tris)); idx=', '.join(str(i) for t in tris for i in t)
    return (f'{pad}def Mesh "{name}"\n{pad}{{\n'+
            f'{p2}point3f[] points = ['+', '.join(fmtv(v) for v in pts)+']\n'+
            f'{p2}int[] faceVertexCounts = [{counts}]\n{p2}int[] faceVertexIndices = [{idx}]\n'+
            f'{p2}uniform token subdivisionScheme = "none"\n{p2}uniform bool doubleSided = true\n'+
            f'{p2}color3f[] primvars:displayColor = [{fmtv(color)}]\n'+
            f'{p2}custom string simulationStatus = "unmeasured_occlusion_proxy"\n'+
            f'{pad}}}\n')

def usd_camera(cam):
    o=cam['optics'];W,H=o['resolution'];nm=cam['id']+'_'+cam['name']
    pos=np.array(cam['position_mm'])*.001
    s=f'        def Camera "{nm}"\n        {{\n'
    s+=f'            double3 xformOp:translate = {fmtv(pos)}\n'
    s+=f'            quatd xformOp:orient = {fmtv(cam["q_B_usd_wxyz"])}\n'
    s+='            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:orient"]\n'
    s+='            token projection = "perspective"\n'
    s+=f'            float horizontalAperture = 0.1\n            float verticalAperture = {0.1*H/W:.12g}\n'
    s+=f'            float focalLength = {0.1*o["fx_px"]/W:.12g}\n'
    s+='            float fStop = 0\n            float focusDistance = 1\n            float2 clippingRange = (0.0001, 100)\n'
    s+=f'            custom int2 nominal:resolution = ({W}, {H})\n            custom double nominal:fps = 30\n'
    s+=f'            custom string nominal:cameraId = "{cam["id"]}"\n'
    s+='            custom string nominal:status = "SIMULATION_ASSUMPTION_NOT_FACTORY_CALIBRATION"\n'
    if o['model']=='ideal_equidistant':
        s+='            custom token cameraProjectionType = "fisheyePolynomial"\n'
        attrs={'fthetaWidth':W,'fthetaHeight':H,'fthetaCx':o['cx_px'],'fthetaCy':o['cy_px'],
               'fthetaMaxFov':o['radial_full_fov_deg'],'fthetaPolyA':0,'fthetaPolyB':1/o['fx_px'],
               'fthetaPolyC':0,'fthetaPolyD':0,'fthetaPolyE':0}
        for k,v in attrs.items(): s+=f'            custom float {k} = {v:.12g}\n'
        s+='            custom string nominal:lensEquation = "theta_rad = radius_px / f_px; requires NVIDIA RTX fisheyePolynomial backend"\n'
    return s+'        }\n'

def write_models(c,out):
    out.mkdir(parents=True,exist_ok=True); cams=camera_specs(c);geo=geometry_specs(c)
    groups={};asms={name:cq.Assembly(name=name) for name in ('seven_camera_rig_proxy','wearer_proxy','complete_occlusion_proxy')}
    for g in geo:
        shape=shape_for(g); groups.setdefault(g['group'],[]).append((g,shape))
        color=cq.Color(*COLORS[g['group']])
        asms['complete_occlusion_proxy'].add(shape,name=g['name'],color=color)
        name='wearer_proxy' if g['group'] in ('Wearer','WearerMount') else 'seven_camera_rig_proxy'
        asms[name].add(shape,name=g['name'],color=color)
    for name,asm in asms.items():
        asm.save(str(out/(name+'.step')),exportType='STEP',mode='default')
    # STL is an auxiliary visual mesh, not the authoritative per-part assembly.
    cq.exporters.export(cq.Compound.makeCompound([s for v in groups.values() for _,s in v]),str(out/'complete_occlusion_proxy_mm.stl'))
    usd='#usda 1.0\n(\n    defaultPrim = "SevenCameraRig"\n    metersPerUnit = 1\n    upAxis = "Z"\n    timeCodesPerSecond = 30\n)\n\n'
    usd+='def Xform "SevenCameraRig"\n{\n    custom string designStatus = "SIM-V0.1; all non-PDF dimensions are proposed, not measured"\n'
    usd+='    custom string bodyFrame = "+X forward, +Y wearer left, +Z up; origin C0 optical center"\n'
    for group,items in groups.items():
        usd+=f'    def Xform "{group}"\n    {{\n'
        for g,s in items: usd+=usd_mesh(g['name'],s,COLORS[group])
        usd+='    }\n'
    usd+='    def Xform "Sensors"\n    {\n'
    for cam in cams: usd+=usd_camera(cam)
    usd+='    }\n    def Xform "IMU"\n    {\n'
    usd+=f'        double3 xformOp:translate = {fmtv(np.array(c["layout"]["imu_position_mm"])*.001)}\n'
    usd+='        uniform token[] xformOpOrder = ["xformOp:translate"]\n        custom string typeHint = "mount frame only; attach physical IMU at runtime"\n'
    usd+='        custom string axes = "+X forward, +Y left, +Z up"\n    }\n}\n'
    (out/'seven_camera_rig.usda').write_text(usd,encoding='utf-8')
    # Geometry-independent extrinsics and optical parameters. Direction is always explicit.
    I=transform(np.eye(3),np.array(c['layout']['imu_position_mm'])*.001)
    entries=[]
    for cam in cams:
        T=transform(np.array(cam['R_B_optical']),np.array(cam['position_mm'])*.001)
        e={**cam,'T_B_cameraOptical_m':T.tolist(),'T_cameraOptical_B_m':np.linalg.inv(T).tolist(),
           'T_IMU_cameraOptical_m':(np.linalg.inv(I)@T).tolist(),
           'T_cameraOptical_IMU_m':(np.linalg.inv(T)@I).tolist()}
        entries.append(e)
    data={'design_revision':c['design_revision'],'calibration_type':'NOMINAL_DESIGN_NOT_MEASURED',
          'conventions':c['frame_convention'],'imu':{'T_B_IMU_m':I.tolist(),'T_IMU_B_m':np.linalg.inv(I).tolist(),
          'position_mm':c['layout']['imu_position_mm'],'quaternion_wxyz':[1,0,0,0],
          'output_hz_simulation_default':c['nominal_acquisition']['imu_output_hz'],'noise_parameters':None},
          'cameras':entries}
    conf=out.parent/'config';conf.mkdir(exist_ok=True)
    (conf/'nominal_extrinsics.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (conf/'nominal_extrinsics.yaml').write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
    with (conf/'sensor_poses.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['id','name','x_mm','y_mm','z_mm','optical_forward_B_x','optical_forward_B_y','optical_forward_B_z','image_up_B_x','image_up_B_y','image_up_B_z','q_B_opt_w','q_B_opt_x','q_B_opt_y','q_B_opt_z','q_B_usd_w','q_B_usd_x','q_B_usd_y','q_B_usd_z'])
        for cam in cams:writer.writerow([cam['id'],cam['name_cn'],*cam['position_mm'],*cam['forward_B'],*cam['up_B'],*cam['q_B_optical_wxyz'],*cam['q_B_usd_wxyz']])
        writer.writerow(['I0','IMU',*c['layout']['imu_position_mm'],'','','','','','',1,0,0,0,'','','',''])
    # URDF contains TF only. It intentionally has no invented mass/inertia and is not a physical robot model.
    urdf='<?xml version="1.0"?>\n<!-- SIM-V0.1 nominal TF tree only; meters; NOT factory calibration. -->\n<robot name="seven_camera_nominal_frames">\n  <link name="rig_body"/>\n'
    for cam in cams:
        name=cam['id']+'_optical'; rpy=Rotation.from_matrix(np.array(cam['R_B_optical'])).as_euler('xyz')
        urdf+=f'  <link name="{name}"/>\n  <joint name="rig_to_{name}" type="fixed"><parent link="rig_body"/><child link="{name}"/><origin xyz="'+ ' '.join(f'{v*.001:.12g}' for v in cam['position_mm'])+'" rpy="'+' '.join(f'{v:.12g}' for v in rpy)+'"/></joint>\n'
    urdf+='  <link name="imu_link"/>\n  <joint name="rig_to_imu" type="fixed"><parent link="rig_body"/><child link="imu_link"/><origin xyz="'+' '.join(f'{v*.001:.12g}' for v in c['layout']['imu_position_mm'])+'" rpy="0 0 0"/></joint>\n</robot>\n'
    (out/'seven_camera_frames.urdf').write_text(urdf)
    # Demo is for stage inspection only, not a SLAM benchmark scene.
    demo='''#usda 1.0
(
    defaultPrim = "World"
    metersPerUnit = 1
    upAxis = "Z"
)
def Xform "World"
{
    def Xform "Rig" (
        prepend references = @seven_camera_rig.usda@</SevenCameraRig>
    )
    {
        double3 xformOp:translate = (0, 0, 1.6)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def DomeLight "Light"
    {
        float inputs:intensity = 600
        color3f inputs:color = (1, 1, 1)
    }
    def Cube "Floor"
    {
        double size = 1
        double3 xformOp:translate = (0,0,-0.025)
        double3 xformOp:scale = (6,6,0.05)
        uniform token[] xformOpOrder = ["xformOp:translate","xformOp:scale"]
        color3f[] primvars:displayColor = [(0.6,0.6,0.6)]
    }
    def Cube "ForwardTarget"
    {
        double size = 1
        double3 xformOp:translate = (1.2,0,1.4)
        double3 xformOp:scale = (0.04,0.5,0.5)
        uniform token[] xformOpOrder = ["xformOp:translate","xformOp:scale"]
        color3f[] primvars:displayColor = [(0.8,0.8,0.8)]
    }
}
'''
    (out/'inspection_scene.usda').write_text(demo)
    return data,geo

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--out',type=Path,default=ROOT/'models');a=ap.parse_args()
    d,g=write_models(load_config(a.config),a.out)
    print(f'Created {len(d["cameras"])} camera frames, IMU mount, {len(g)} proxy parts in {a.out}')
