"""Start only the Step 2.1b external figure renderer in the existing runtime."""
import os,sys,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'reports/step2_1b';out.mkdir(parents=True,exist_ok=True)
runtime=root/'.cache/runtime';runtime.mkdir(parents=True,exist_ok=True);runtime.chmod(0o700)
env=os.environ.copy();env.update(OMNI_KIT_ACCEPT_EULA='YES',OMNI_KIT_ALLOW_ROOT='1',XDG_RUNTIME_DIR=str(runtime))
state=root/'outputs/step2_1b/debug/render_status.json';state.parent.mkdir(parents=True,exist_ok=True);state.write_text(json.dumps({'status':'STARTING'}))
with (out/'isaac_fov_figure.log').open('wb') as f:
 p=subprocess.Popen([sys.executable,'-u',str(root/'scripts/isaac_fov_figure.py')],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'pid':p.pid,'log':'reports/step2_1b/isaac_fov_figure.log'}))
