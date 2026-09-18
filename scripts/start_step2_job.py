import os,subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];runtime=root/'.cache/runtime';runtime.mkdir(parents=True,exist_ok=True);runtime.chmod(0o700)
env=os.environ.copy();env.update(OMNI_KIT_ACCEPT_EULA='YES',OMNI_KIT_ALLOW_ROOT='1',XDG_RUNTIME_DIR=str(runtime))
(root/'reports/step2').mkdir(parents=True,exist_ok=True)
(root/'outputs/step2').mkdir(parents=True,exist_ok=True)
(root/'outputs/step2/render_status.json').write_text(json.dumps(dict(status='RUNNING')))
with (root/'reports/step2/isaac_step2.log').open('wb') as stream:
 p=subprocess.Popen([sys.executable,'-u',str(root/'scripts/isaac_step2.py')],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(pid=p.pid)))
