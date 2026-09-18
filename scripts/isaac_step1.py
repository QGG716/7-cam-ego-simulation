"""Isaac Sim 6.0.1.0 static capture; original rig referenced without geometry edits."""
import argparse,json,sys,hashlib,math,time
import traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
p=argparse.ArgumentParser()
p.add_argument('--task',choices=['angles','capture','all'],default='all')
p.add_argument('--cameras',default='C0,C1,C3')
p.add_argument('--mode',choices=['ideal','body','worn'],default='ideal')
a=p.parse_args()
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','width':1280,'height':960,
                   'anti_aliasing':0,'multi_gpu':False})
try:
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    from pxr import Usd,UsdGeom,UsdLux,UsdShade,Sdf,Gf
    import omni.usd
    import omni.replicator.core as rep
    import omni.timeline
    import carb
    from rig_common import load_config,camera_specs,pixel_rays,camera_rotation,quat_wxyz
    from projection import angle_targets,project
    c=load_config();cams=camera_specs(c)
    sha=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
    output=ROOT/'outputs/step1';output.mkdir(parents=True,exist_ok=True)
    (output/'run_status.json').write_text(json.dumps(dict(status='RUNNING',task=a.task,config_sha256=sha)))
    timeline=omni.timeline.get_timeline_interface()
    settings=carb.settings.get_settings()
    settings.set('/rtx/post/aa/op',0)
    settings.set('/rtx/post/histogram/enabled',False)
    settings.set('/rtx/post/tonemap/filmIso',100.)

    def open_layer(filename):
        omni.usd.get_context().open_stage(str(filename))
        for _ in range(12):app.update()
        stage=omni.usd.get_context().get_stage()
        assert stage and abs(UsdGeom.GetStageMetersPerUnit(stage)-1)<1e-10
        timeline.pause();timeline.set_current_time(0.)
        return stage

    def mode(stage,value):
        for group in ['Housing','Accessories','WearerMount','Wearer']:
            prim=stage.GetPrimAtPath('/World/Rig/'+group)
            assert prim
            visible=value=='worn' or (value=='body' and group in ('Housing','Accessories'))
            UsdGeom.Imageable(prim).GetVisibilityAttr().Set('inherited' if visible else 'invisible')

    def material(stage,path,color,emission=False):
        mat=UsdShade.Material.Define(stage,path)
        shader=UsdShade.Shader.Define(stage,path+'/Shader');shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.75)
        if emission:shader.CreateInput('emissiveColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
        return mat

    def cube(stage,path,pos,size,color):
        obj=UsdGeom.Cube.Define(stage,path);obj.CreateSizeAttr(1.)
        obj.AddTranslateOp().Set(Gf.Vec3d(*pos));obj.AddScaleOp().Set(Gf.Vec3f(*size))
        obj.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        return obj

    def verify(stage):
        result=[]
        for cam in cams:
            path=cam['prim_path'].replace('/SevenCameraRig','/World/Rig')
            prim=stage.GetPrimAtPath(path);assert prim.IsA(UsdGeom.Camera)
            assert np.allclose(prim.GetAttribute('xformOp:translate').Get(),np.array(cam['position_mm'])*.001,atol=1e-10)
            q=prim.GetAttribute('xformOp:orient').Get()
            assert np.allclose([q.GetReal(),*q.GetImaginary()],cam['q_B_usd_wxyz'],atol=1e-10)
            assert prim.GetAttribute('sim:configSha256').Get()==sha
            assert abs(prim.GetAttribute('clippingRange').Get()[0]-.0001)<1e-10
            attrs={str(x.GetName()):str(x.Get()) for x in prim.GetAttributes()
                   if 'lensdistortion' in str(x.GetName()) or 'ftheta' in str(x.GetName()) or 'sim:' in str(x.GetName())}
            if cam['id']=='C0':
                assert prim.HasAPI('OmniLensDistortionOpenCvPinholeAPI')
                for key in ('fx','fy','cx','cy'):
                    actual=prim.GetAttribute('omni:lensdistortion:opencvPinhole:'+key).Get()
                    assert np.isclose(actual,cam['optics'][key+'_px'],atol=1e-4)
            else:
                assert not any('LensDistortion' in v for v in prim.GetAppliedSchemas())
                assert prim.GetAttribute('cameraProjectionType').Get()=='fisheyePolynomial'
            result.append(dict(id=cam['id'],schemas=list(prim.GetAppliedSchemas()),attributes=attrs))
        (output/'usd_runtime_verification.json').write_text(json.dumps(result,indent=2))

    def render(stage,path,resolution,warm=8):
        product=rep.create.render_product(path,tuple(resolution))
        rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([product])
        for _ in range(warm):app.update()
        timeline.pause();timeline.set_current_time(0.)
        rep.orchestrator.step(rt_subframes=8,delta_time=0.0,pause_timeline=True)
        arr=np.asarray(rgb.get_data()).copy()
        if arr.shape[:2]!=tuple(resolution[::-1]):raise RuntimeError(f'Invalid RGB shape {arr.shape}')
        rgb.detach([product]);product.destroy()
        assert abs(timeline.get_current_time())<1e-9
        return arr[...,:3].astype(np.uint8)

    def save_image(cam,arr,directory,extra):
        directory.mkdir(parents=True,exist_ok=True)
        _,mask=pixel_rays(cam)
        raw=arr.copy();arr=arr.copy();arr[~mask]=0
        Image.fromarray(arr).save(directory/(cam['id']+'.png'))
        Image.fromarray(mask.astype(np.uint8)*255).save(directory/(cam['id']+'_valid_mask.png'))
        meta=dict(camera_id=cam['id'],width=arr.shape[1],height=arr.shape[0],version=c['design_revision'],config_sha256=sha,
                  projection=cam['optics'],simulation_time_seconds=timeline.get_current_time(),static_scene_id='step1-static-0',
                  pixel_convention=c['simulation']['pixel_convention'],invalid_region='masked to black; not structural occlusion',
                  backend='native OpenCV pinhole' if cam['id']=='C0' else 'legacy RTX fisheyePolynomial',**extra)
        (directory/(cam['id']+'.json')).write_text(json.dumps(meta,indent=2))
        return arr

    def create_inspection():
        filename=ROOT/'scenes/inspection_scene.usda'
        filename.write_text('#usda 1.0\n(defaultPrim="World"\n metersPerUnit=1\n upAxis="Z"\n subLayers=[@rig_v0.2.usda@])\n')
        stage=open_layer(filename)
        UsdGeom.Xform.Define(stage,'/World/Environment')
        light=UsdLux.DomeLight.Define(stage,'/World/Environment/Light');light.CreateIntensityAttr(600.)
        # Checker planes and asymmetric color bars give each optical direction recognizable content.
        for plane,height in [('Floor',-.025),('Ceiling',3.225)]:
            for ix in range(-6,7):
                for iy in range(-6,7):
                    shade=.19 if (ix+iy)%2 else .68
                    cube(stage,f'/World/Environment/{plane}/tile_{ix+6}_{iy+6}',(ix*.4,iy*.4,height),(.399,.399,.05),(shade,shade,shade))
            cube(stage,f'/World/Environment/{plane}/red_x',(1.,0.,height+(.035 if plane=='Floor' else -.035)),(1.2,.10,.02),(.9,.06,.04))
            cube(stage,f'/World/Environment/{plane}/green_y',(0.,.8,height+(.035 if plane=='Floor' else -.035)),(.10,.9,.02),(.04,.8,.1))
        for i,(pos,size,col) in enumerate([
            ((2.3,0,1.6),(.05,2.8,2.3),(.1,.2,.6)),
            ((1.9,.65,1.65),(.06,.18,1.5),(.9,.2,.05)),
            ((1.8,-.65,1.6),(.08,.5,.3),(.05,.85,.2)),
            ((0,2.6,1.6),(3.8,.05,2.8),(.25,.65,.8)),
            ((0,-2.6,1.6),(3.8,.05,2.8),(.8,.48,.15)),
            ((-2.3,0,1.6),(.05,4.8,2.8),(.48,.18,.55))]):
            cube(stage,f'/World/Environment/Marker_{i}',pos,size,col)
        for iy in range(7):
            for iz in range(5):
                shade=.85 if (iy+iz)%2 else .08
                cube(stage,f'/World/Environment/FrontGrid/t_{iy}_{iz}',(2.26,(iy-3)*.35,.85+iz*.35),(.02,.33,.33),(shade,shade,shade))
        mode(stage,'worn');stage.GetRootLayer().Save()
        return stage

    def angles():
        results=[]
        for cid in a.cameras.split(','):
            cam=next(v for v in cams if v['id']==cid)
            name=ROOT/f'scenes/angle_{cid}.usda'
            name.write_text('#usda 1.0\n(defaultPrim="World"\n metersPerUnit=1\n upAxis="Z"\n subLayers=[@rig_v0.2.usda@])\n')
            stage=open_layer(name);mode(stage,'ideal');verify(stage)
            mat=material(stage,'/World/Test/White',(1.,1.,1.),True)
            center=np.array(cam['position_mm'])*.001+np.array(c['simulation']['rig_world_translation_m'])
            R=np.array(cam['R_B_optical'])
            targets=angle_targets(cam)
            for i,t in enumerate(targets):
                sphere=UsdGeom.Sphere.Define(stage,f'/World/Test/Target_{i}')
                sphere.CreateRadiusAttr(t['radius_m']);sphere.AddTranslateOp().Set(Gf.Vec3d(*(center+R@t['ray'])))
                UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(mat)
                sphere.GetVisibilityAttr().Set('invisible')
            stage.GetRootLayer().Save()
            directory=output/'angles'/cid;directory.mkdir(parents=True,exist_ok=True)
            for i,t in enumerate(targets):
                sphere=UsdGeom.Imageable(stage.GetPrimAtPath(f'/World/Test/Target_{i}'))
                sphere.GetVisibilityAttr().Set('inherited')
                arr=render(stage,cam['prim_path'].replace('/SevenCameraRig','/World/Rig'),cam['optics']['resolution'])
                Image.fromarray(arr).save(directory/(t['name']+'_raw.png'))
                _,valid=pixel_rays(cam)
                arr[~valid]=0
                Image.fromarray(arr).save(directory/(t['name']+'.png'))
                # Whole-image measurement; no theoretical pixel supplied to the detector.
                from scipy.ndimage import label
                signal=arr.mean(axis=2)>80
                labels,count=label(signal)
                blobs=[]
                for lab in range(1,count+1):
                    yy,xx=np.where(labels==lab)
                    if len(xx)>=2:
                        weights=arr[yy,xx].mean(axis=1)
                        blobs.append(dict(area=len(xx),uv=[float(np.average(xx+.5,weights=weights)),float(np.average(yy+.5,weights=weights))]))
                detected=len(blobs)==1
                ambiguous=len(blobs)>1
                uv=blobs[0]['uv'] if detected else None
                error=float(np.linalg.norm(np.array(uv)-t['theoretical_uv_px'])) if detected else None
                status='NEEDS_REVIEW' if ambiguous else ('PASS' if detected==t['theoretical_visible'] and (not detected or error<=2.) else 'FAIL')
                record=dict(camera_id=cid,**t,detected_uv_px=uv,actual_visible=detected,residual_px=error,blobs=blobs,status=status,
                            image=str((directory/(t['name']+'.png')).relative_to(ROOT)),simulation_time_seconds=timeline.get_current_time())
                results.append(record)
                print('ANGLE',cid,t['name'],status,uv,error,flush=True)
                sphere.GetVisibilityAttr().Set('invisible')
                (output/'angle_results.json').write_text(json.dumps(results,indent=2))
        return results

    def overview(stage):
        mode(stage,'worn')
        UsdGeom.Imageable(stage.GetPrimAtPath('/World/Environment')).GetVisibilityAttr().Set('invisible')
        light=UsdLux.DomeLight.Define(stage,'/World/OverviewLight');light.CreateIntensityAttr(900.)
        pos=np.array([.38,-.48,1.94]);target=np.array([-.085,0,1.59])
        R=camera_rotation(target-pos,[0,0,1]);q=quat_wxyz(R@np.diag([1.,-1.,-1.]))
        camera=UsdGeom.Camera.Define(stage,'/World/OverviewCamera')
        camera.AddTranslateOp().Set(Gf.Vec3d(*pos));camera.AddOrientOp().Set(Gf.Quatf(q[0],Gf.Vec3f(*q[1:])))
        camera.CreateHorizontalApertureAttr(36.);camera.CreateVerticalApertureAttr(27.);camera.CreateFocalLengthAttr(42.)
        camera.CreateClippingRangeAttr(Gf.Vec2f(.0001,100.));camera.CreateFStopAttr(0.)
        arr=render(stage,'/World/OverviewCamera',(1600,1200),12)
        Image.fromarray(arr).save(output/'worn_overview_raw.png')
        im=Image.fromarray(arr);draw=ImageDraw.Draw(im)
        try:font=ImageFont.truetype('DejaVuSans.ttf',24)
        except OSError:font=ImageFont.load_default()
        def pix(world):
            d=R.T@(world-pos)
            return (float(800+1600*42/36*d[0]/d[2]),float(600+1200*42/27*d[1]/d[2]))
        labels=[(1030,430),(1130,340),(1040,545),(710,245),(740,670),(1260,470),(1260,720)]
        for cam,where in zip(cams,labels):
            center=np.array(cam['position_mm'])*.001+np.array(c['simulation']['rig_world_translation_m'])
            u,v=pix(center);end=pix(center+np.array(cam['forward_B'])*.035)
            draw.ellipse((u-5,v-5,u+5,v+5),fill='yellow')
            draw.line(((u,v),end),fill='yellow',width=4)
            vec=np.array(end)-[u,v];vec/=max(np.linalg.norm(vec),1)
            perp=np.array([-vec[1],vec[0]])
            draw.polygon([end,tuple(np.array(end)-vec*12+perp*5),tuple(np.array(end)-vec*12-perp*5)],fill='yellow')
            draw.line(((u,v),where),fill=(180,220,255),width=2)
            draw.text(where,cam['id']+' '+('front +X' if cam['id'] in ('C0','C1','C2') else ('up +Z' if cam['id'] in ('C3','C5') else 'down -Z')),fill='white',font=font,stroke_width=2,stroke_fill='black')
        draw.text((35,30),'SIM-V0.2-vfov130 | worn | nominal unmeasured structure',font=font,fill='white')
        draw.text((35,70),'Yellow: optical center + optical axis; labels are post-render overlays',font=font,fill='white')
        im.save(output/'worn_overview.png')
        (output/'worn_overview.json').write_text(json.dumps(dict(version=c['design_revision'],config_sha256=sha,mode='worn',
            width=1600,height=1200,simulation_time_seconds=0.,camera_position_world_m=pos.tolist(),camera_R_world_optical=R.tolist(),
            annotation='post-render projection of exact camera centers/axis; never present in sensor images'),indent=2))
        stage.GetRootLayer().Export(str(ROOT/'scenes/worn_overview.usda'))

    angle_records=angles() if a.task in ('angles','all') else []
    if a.task in ('capture','all'):
        stage=create_inspection();verify(stage);mode(stage,a.mode)
        for cam in cams:
            arr=render(stage,cam['prim_path'].replace('/SevenCameraRig','/World/Rig'),cam['optics']['resolution'])
            save_image(cam,arr,output/a.mode,dict(mode=a.mode))
            print('CAPTURED',cam['id'],arr.shape,flush=True)
        overview(stage)
    (output/'run_status.json').write_text(json.dumps(dict(status='PASS' if all(x['status']=='PASS' for x in angle_records) else 'NEEDS_REVIEW',
        angle_checks=len(angle_records),angle_pass=sum(x['status']=='PASS' for x in angle_records),task=a.task,version=c['design_revision'],
        config_sha256=sha,isaac_version='6.0.1.0',note='Static sequential capture only; no FPS/sync/IMU/SLAM validation'),indent=2))
except Exception as exc:
    traceback.print_exc()
    (ROOT/'outputs/step1/run_status.json').write_text(json.dumps(dict(status='FAILED',error=str(exc),traceback=traceback.format_exc()),indent=2))
    raise
finally:
    app.close()
