"""Start a scoped v2 job, keeping diagnostics out of the public repository."""
import os,sys,json,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[1]; out=r/'reports/step2_1b_v2';out.mkdir(parents=True,exist_ok=True)
name=sys.argv[1];assert name in ['probe_worker_v2','prepare_worker_v2','render_worker_v2','apply_refinement_v2']
runtime=r/'.cache/runtime';runtime.mkdir(parents=True,exist_ok=True);runtime.chmod(0o700)
env=os.environ.copy();env.update(OMNI_KIT_ACCEPT_EULA='YES',OMNI_KIT_ALLOW_ROOT='1',XDG_RUNTIME_DIR=str(runtime))
with (out/(name+'.log')).open('wb') as f:
 p=subprocess.Popen([sys.executable,'-u',str(r/'scripts'/(name+'.py'))],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'pid':p.pid,'log':str(out/(name+'.log'))}))
