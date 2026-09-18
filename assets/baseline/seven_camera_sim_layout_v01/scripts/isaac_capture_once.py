#!/usr/bin/env python3
"""Open the nominal rig and capture one set of seven images in Isaac.
Run using Isaac's python.sh, not a normal Python environment.
No SLAM, timed capture, real IMU data, noise or motion is implemented here.
Target API: standard USD + Replicator. Runtime test on target Isaac still required.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--headless',action='store_true')
p.add_argument('--occlusion',choices=['ideal','body','worn'],default='worn')
p.add_argument('--output',type=Path,default=ROOT/'isaac_output')
p.add_argument('--projection-check',choices=['C3','C4','C5','C6'],help='Hide proxies and render angular test targets for one 220-degree camera')
a=p.parse_args()

from isaacsim import SimulationApp
app=SimulationApp({'headless':a.headless})
try:
    import numpy as np
    from pxr import Usd,UsdGeom,UsdLux,UsdShade,Sdf,Gf
    import omni.usd
    import omni.replicator.core as rep
    from PIL import Image

    omni.usd.get_context().open_stage(str(ROOT/'models/inspection_scene.usda'))
    for _ in range(8):app.update()
    stage=omni.usd.get_context().get_stage()
    if not stage:raise RuntimeError('Cannot open inspection_scene.usda')
    if abs(UsdGeom.GetStageMetersPerUnit(stage)-1)>1e-12:raise RuntimeError('Expected USD metersPerUnit=1')
    data=json.loads((ROOT/'config/nominal_extrinsics.json').read_text(encoding='utf-8'))
    rig='/World/Rig'
    mode='ideal' if a.projection_check else a.occlusion
    for group in ['Housing','Accessories','WearerMount','Wearer']:
        prim=stage.GetPrimAtPath(f'{rig}/{group}')
        if not prim:raise RuntimeError(f'Missing rig group: {group}')
        visible=(mode=='worn') or (mode=='body' and group in ['Housing','Accessories'])
        UsdGeom.Imageable(prim).GetVisibilityAttr().Set('inherited' if visible else 'invisible')

    xcache=UsdGeom.XformCache()
    rigworld=xcache.GetLocalToWorldTransform(stage.GetPrimAtPath(rig))
    cam_paths={}
    for cam in data['cameras']:
        path=cam['prim_path'].replace('/SevenCameraRig',rig,1);prim=stage.GetPrimAtPath(path)
        if not prim or not prim.IsA(UsdGeom.Camera):raise RuntimeError(f'Missing camera: {path}')
        pos=prim.GetAttribute('xformOp:translate').Get()
        expected=np.asarray(cam['position_mm'])*.001
        if not np.allclose(pos,expected,atol=1e-10):raise RuntimeError(f'Position mismatch for {cam["id"]}')
        q=prim.GetAttribute('xformOp:orient').Get()
        qarray=[q.GetReal(),*q.GetImaginary()]
        if not (np.allclose(qarray,cam['q_B_usd_wxyz']) or np.allclose(-np.array(qarray),cam['q_B_usd_wxyz'])):
            raise RuntimeError(f'Quaternion mismatch for {cam["id"]}')
        # Legacy f-theta deliberately used for broad-angle rays on target 6.0.
        # Do not apply a LUT or another lens schema on top; it would override these values.
        if cam['optics']['model']=='ideal_equidistant':
            if prim.GetAttribute('cameraProjectionType').Get()!='fisheyePolynomial':
                raise RuntimeError(f'Fisheye attributes missing for {cam["id"]}')
        cam_paths[cam['id']]=path

    projection_targets=[]
    if a.projection_check:
        for path in ('/World/Floor','/World/ForwardTarget'):
            UsdGeom.Imageable(stage.GetPrimAtPath(path)).GetVisibilityAttr().Set('invisible')
        cam=next(x for x in data['cameras'] if x['id']==a.projection_check)
        R=np.asarray(cam['R_B_optical']);center=np.asarray(cam['position_mm'])*.001
        o=cam['optics']
        material=UsdShade.Material.Define(stage,'/World/ProjectionCheck/White')
        shader=UsdShade.Shader.Define(stage,'/World/ProjectionCheck/White/Shader');shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1,1,1))
        shader.CreateInput('emissiveColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1,1,1))
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
        for angle in [0,30,60,85,95,105,115]:
            theta=math.radians(angle)
            ray=np.array([math.sin(theta),0,math.cos(theta)])
            pb=center+R@ray # one meter from the selected nominal optical center
            pw=rigworld.Transform(Gf.Vec3d(*pb))
            sphere=UsdGeom.Sphere.Define(stage,f'/World/ProjectionCheck/Target_{angle:03d}')
            sphere.CreateRadiusAttr(.009);sphere.AddTranslateOp().Set(pw)
            UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(material)
            projection_targets.append({'angle_deg':angle,'position_world_m':list(pw),
                'expected_visible':angle<=110,'expected_u_px':o['cx_px']+o['fx_px']*theta,
                'expected_v_px':o['cy_px'],'note':'F-theta angular check; no proxy occlusion'})

    # One render product per physical camera preserves different resolutions.
    products=[];ann=[]
    for cam in data['cameras']:
        if a.projection_check and cam['id']!=a.projection_check:continue
        rp=rep.create.render_product(cam_paths[cam['id']],tuple(cam['optics']['resolution']))
        rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([rp])
        products.append(rp);ann.append((cam,rgb))
    for _ in range(20):app.update()
    rep.orchestrator.step(rt_subframes=4)
    for _ in range(4):app.update()
    a.output.mkdir(parents=True,exist_ok=True)
    for cam,rgb in ann:
        arr=np.asarray(rgb.get_data())
        if arr.ndim!=3 or arr.shape[0:2]!=tuple(cam['optics']['resolution'][::-1]):
            raise RuntimeError(f'Invalid rendered shape for {cam["id"]}: {arr.shape}')
        Image.fromarray(arr.astype(np.uint8)).save(a.output/f'{cam["id"]}_{cam["name"]}_{mode}.png')
    manifest={'status':'CAPTURE_ONLY_NOT_A_SLAM_OR_SYNC_ACCEPTANCE_TEST','occlusion_mode':mode,
        'projection_backend':'legacy RTX fisheyePolynomial for equidistant cameras',
        'projection_check':a.projection_check,'targets':projection_targets,
        'warning':'Manual pixel/angle check required; merely loading a Camera prim does not validate 220-degree rendering.'}
    (a.output/'capture_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(f'Capture saved to {a.output}. No IMU or SLAM was run.')
finally:
    app.close()
