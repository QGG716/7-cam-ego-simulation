"""Render only Step 2.1b external views in an already configured remote project."""
import getpass,json,shlex,time,stat,posixpath
from pathlib import Path
import paramiko
ROOT=Path(__file__).resolve().parents[1];config=json.loads((ROOT/'config/environment.local.json').read_text());remote=config['remote_project'];assert remote=='/root/autodl-tmp/7-cam-ego-simulation-step1'
client=paramiko.SSHClient();known=ROOT/'.ssh/known_hosts'
if known.exists():client.load_host_keys(str(known))
client.set_missing_host_key_policy(paramiko.AutoAddPolicy());client.connect(config['ssh_host'],port=config['ssh_port'],username=config['ssh_user'],password=getpass.getpass('SSH password: '),look_for_keys=False,allow_agent=False,timeout=20)
def execute(command):
 _,out,err=client.exec_command(command,timeout=60);stdout=out.read().decode();stderr=err.read().decode();code=out.channel.recv_exit_status()
 if code:raise RuntimeError(stderr or stdout)
 return stdout
try:
 sftp=client.open_sftp()
 def mkdir(path):
  try:sftp.stat(path)
  except FileNotFoundError:mkdir(posixpath.dirname(path));sftp.mkdir(path)
 for relative in ['scripts/isaac_fov_figure.py','scripts/start_fov_figure_job.py','reports/step2_1b/input_manifest.json']:
  mkdir(posixpath.dirname(remote+'/'+relative));sftp.put(str(ROOT/relative),remote+'/'+relative)
 info=json.loads(execute(shlex.quote(config['remote_python'])+' '+shlex.quote(remote+'/scripts/start_fov_figure_job.py')))
 deadline=time.monotonic()+1200
 while time.monotonic()<deadline:
  state=execute('ps -p '+str(info['pid'])+' -o stat= || true').strip()
  if not state or state.startswith('Z'):break
  print('External figure rendering; log:',info['log'],flush=True);time.sleep(10)
 else:raise TimeoutError('Inspect project log; job was not terminated.')
 def fetch(relative):
  path=remote+'/'+relative
  if stat.S_ISDIR(sftp.stat(path).st_mode):
   for name in sftp.listdir(path):fetch(relative+'/'+name)
  else:
   local=ROOT/relative;local.parent.mkdir(parents=True,exist_ok=True);sftp.get(path,str(local))
 fetch('outputs/step2_1b/debug');fetch('reports/step2_1b/isaac_fov_figure.log')
 result=json.loads((ROOT/'outputs/step2_1b/debug/render_status.json').read_text());assert result['status']=='PASS',result
 print('Four external views downloaded; no formal sensor frames rendered.')
finally:client.close()
