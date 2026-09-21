"""Bake ideal equidistant rays into native RTX LUT textures, without RGB remapping."""
import os
os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
import sys,json,hashlib
from pathlib import Path
import numpy as np
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from rig_common import load_config,camera_specs
from projection import unproject

def main():
 out=ROOT/'config/step2_1b_v6/lut';out.mkdir(parents=True,exist_ok=True);cams={c['id']:c for c in camera_specs(load_config())};records=[]
 # Octahedral lookup coordinates have forward at the texture center (RTX Z-flip convention).
 size=2048;x,y=np.meshgrid((np.arange(size)+.5)/size*2-1,(np.arange(size)+.5)/size*2-1);z=1-abs(x)-abs(y);fold=np.maximum(-z,0);x=x-np.sign(x)*fold;y=y-np.sign(y)*fold;norm=np.sqrt(x*x+y*y+z*z);x/=norm;y/=norm;z/=norm;rho=np.hypot(x,y);theta=np.arctan2(rho,z);k=np.divide(theta,rho,out=np.zeros_like(theta),where=rho>0)
 for profile,cid in [('front','C1'),('surround','C3')]:
  c=cams[cid];o=c['optics'];w,h=o['resolution'];u,v=np.meshgrid(np.arange(w)+.5,np.arange(h)+.5);directions=unproject(c,np.stack([u,v],axis=-1))*[1,-1,-1];entry=directions.astype(np.float32)
  exitmap=np.stack([.5+o['fx_px']*k*x/w,.5-o['fy_px']*k*y/h,np.zeros_like(x)],axis=-1).astype(np.float32)
  for suffix,array in [('enter',entry),('exit',exitmap)]:
   path=out/(profile+'_'+suffix+'.exr');assert cv2.imwrite(str(path),array[...,::-1]);decoded=cv2.imread(str(path),cv2.IMREAD_UNCHANGED)[...,::-1];assert np.array_equal(decoded,array)
   records.append(dict(file=path.relative_to(ROOT).as_posix(),shape=list(array.shape),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),float32_roundtrip_exact=True))
  print('LUT',profile,flush=True)
 (out/'manifest.json').write_text(json.dumps(dict(records=records,method='Native direction texture at sensor pixel centers; inverse NDC texture uses octahedral directions with renderer Z convention; rectangular equidistant fx/fy; no RGB postwarp',specification='https://docs.omniverse.nvidia.com/materials-and-rendering/latest/cameras.html'),indent=2)+'\n')
if __name__=='__main__':main()
