"""Step 2 full-resolution first-hit analysis; B-frame mm internally, metres on disk."""
import sys,json,hashlib,csv
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs,geometry_specs,pixel_rays,nearest_hit
OUT=ROOT/'outputs/step2'
OPTIONS=json.loads((ROOT/'config/step2_analysis.json').read_text())
SHA=hashlib.sha256((ROOT/'config/rig_sim_v0.2.json').read_bytes()).hexdigest()
def components():
    return [dict(id=i+1,usd_path='/World/Rig/'+g['group']+'/'+g['name'],**g) for i,g in enumerate(geometry_specs(load_config()))]
def inside(origin,obj):
    p=np.array(origin,float)
    if obj['kind']=='box':return bool(np.all(np.abs(p-obj['center_mm'])<np.array(obj['size_mm'])/2))
    if obj['kind']=='ellipsoid':return bool(np.sum(((p-obj['center_mm'])/obj['radii_mm'])**2)<1)
    a=np.array(obj['a_mm']);v=np.array(obj['b_mm'])-a;length=np.linalg.norm(v);v=v/length;h=(p-a)@v
    return bool(0<h<length and np.linalg.norm(p-a-h*v)<obj['radius_mm'])
def trace(origin,rays,valid,objects):
    shape=valid.shape;rr=rays.reshape(-1,3);vv=valid.ravel()
    ids=np.zeros(vv.size,np.uint16);dist=np.full(vv.size,np.nan,np.float32)
    for start in range(0,len(rr),OPTIONS['chunk_rays']):
        stop=min(start+OPTIONS['chunk_rays'],len(rr));d=rr[start:stop];best=np.full(len(d),np.inf);labels=np.zeros(len(d),np.uint16)
        for obj in objects:
            with np.errstate(invalid='ignore',divide='ignore'):hit=nearest_hit(origin,d,obj)
            update=(hit<best)&vv[start:stop];best[update]=hit[update];labels[update]=obj['id']
        ids[start:stop]=labels;dist[start:stop]=np.where(np.isfinite(best),best*.001,np.nan)
    return ids.reshape(shape),dist.reshape(shape)
def run():
    OUT.mkdir(parents=True,exist_ok=True);objs=components();(OUT/'components.json').write_text(json.dumps(objs,indent=2))
    inside_records=[];rows=[]
    for cam in camera_specs(load_config()):
        rays,valid=pixel_rays(cam,stride=1);nv=int(valid.sum());body=None
        for obj in objs:
            if inside(cam['position_mm'],obj):inside_records.append(dict(camera_id=cam['id'],component_id=obj['id'],name=obj['name']))
        for mode,groups in OPTIONS['modes'].items():
            ids,dist=trace(cam['position_mm'],rays,valid,[g for g in objs if g['group'] in groups]);blocked=ids>0
            if mode=='ideal':assert not blocked.any()
            if mode=='body':body=blocked.copy()
            added=blocked&~body if mode=='worn' else np.zeros_like(blocked)
            if mode=='worn':assert not (body&~blocked).any()
            state=np.where(valid,np.where(blocked,2,1),0).astype(np.uint8)
            directory=OUT/mode;directory.mkdir(exist_ok=True)
            np.savez_compressed(directory/(cam['id']+'_analytic.npz'),valid=valid,blocked=blocked,first_hit_id=ids,hit_distance_m=dist,state=state,added_blocked=added)
            for name,mask in [('valid',valid),('blocked',blocked),('added',added)]:Image.fromarray(mask.astype(np.uint8)*255).save(directory/(cam['id']+'_'+name+'.png'))
            Image.fromarray(ids).save(directory/(cam['id']+'_first_hit_id.png'))
            contributions=[]
            for obj in objs:
                yy,xx=np.where(ids==obj['id']);n=len(xx)
                contributions.append(dict(component_id=obj['id'],name=obj['name'],group=obj['group'],N_blocked=n,pixel_ratio=n/nv,centroid_uv_px=[float(xx.mean()+.5),float(yy.mean()+.5)] if n else None,bbox_xyxy=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())] if n else None))
            nb=int(blocked.sum());assert sum(o['N_blocked'] for o in contributions)==nb
            row=dict(camera_id=cam['id'],mode=mode,N_valid=nv,N_blocked=nb,occlusion_pixel_ratio=nb/nv,N_added=int(added.sum()),added_pixel_ratio=int(added.sum())/nv,components=contributions,groups={g:sum(x['N_blocked'] for x in contributions if x['group']==g)/nv for g in OPTIONS['modes']['worn']})
            rows.append(row);print(cam['id'],mode,nb,nv,nb/nv,flush=True)
    (OUT/'camera_occlusion_summary.json').write_text(json.dumps(dict(config_sha256=SHA,stride=1,metric='occlusion_pixel_ratio',rows=rows,optical_centers_inside_opaque_geometry=inside_records),indent=2))
    keys=['camera_id','mode','N_valid','N_blocked','occlusion_pixel_ratio','N_added','added_pixel_ratio']
    with (OUT/'camera_occlusion_summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows({k:r[k] for k in keys} for r in rows)
if __name__=='__main__':run()
