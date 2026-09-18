"""Start one bounded Step 1 job in the existing Isaac environment."""
import argparse,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--task',choices=['all','angles','capture'],default='all');a=p.parse_args()
root=Path(__file__).resolve().parents[1]
runtime=root/'.cache/runtime';runtime.mkdir(parents=True,exist_ok=True);runtime.chmod(0o700)
(root/'reports').mkdir(exist_ok=True)
env=os.environ.copy();env.update(OMNI_KIT_ACCEPT_EULA='YES',OMNI_KIT_ALLOW_ROOT='1',XDG_RUNTIME_DIR=str(runtime))
log=root/'reports'/('isaac_'+a.task+'.log')
with log.open('wb') as stream:
    process=subprocess.Popen([sys.executable,'-u',str(root/'scripts/isaac_step1.py'),'--task',a.task],
        cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
info=dict(pid=process.pid,task=a.task,log=str(log.relative_to(root)))
(root/'reports/current_job.json').write_text(json.dumps(info,indent=2))
print(json.dumps(info))
