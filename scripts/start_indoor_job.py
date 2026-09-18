"""Bounded project-local Isaac job launcher, no environment installation."""
import os,sys,subprocess,json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--script',default='probe_indoor_assets.py');a=p.parse_args()
assert a.script in ['probe_indoor_assets.py','isaac_indoor_wearer.py','inspect_indoor_geometry.py']
root=Path(__file__).resolve().parents[1];runtime=root/'.cache/runtime';runtime.mkdir(parents=True,exist_ok=True);runtime.chmod(0o700)
out=root/'reports/step2_1';out.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env.update(OMNI_KIT_ACCEPT_EULA='YES',OMNI_KIT_ALLOW_ROOT='1',XDG_RUNTIME_DIR=str(runtime))
with (out/(a.script+'.log')).open('wb') as f:
 proc=subprocess.Popen([sys.executable,'-u',str(root/'scripts'/a.script)],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'pid':proc.pid,'log':'reports/step2_1/'+a.script+'.log'}))
