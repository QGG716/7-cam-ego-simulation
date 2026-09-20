"""Reproduce v3 using only the existing configured remote runtime and local figure tools."""
import getpass,json,shlex,time,stat,posixpath,subprocess,sys
from pathlib import Path
import paramiko
ROOT=Path(__file__).resolve().parents[1];config=json.loads((ROOT/'config/environment.local.json').read_text());remote=config['remote_project'];python=config['remote_python']
client=paramiko.SSHClient();known=ROOT/'.ssh/known_hosts'
if known.exists():client.load_host_keys(str(known))
client.set_missing_host_key_policy(paramiko.RejectPolicy());client.connect(config['ssh_host'],port=config['ssh_port'],username=config['ssh_user'],password=getpass.getpass('SSH password: '),look_for_keys=False,allow_agent=False,timeout=20)
def execute(command):
 _,out,err=client.exec_command(command,timeout=300);stdout=out.read().decode();stderr=err.read().decode();code=out.channel.recv_exit_status()
 if code:raise RuntimeError(stderr or stdout)
 return stdout
try:
 sftp=client.open_sftp()
 for path in ROOT.glob('scripts/*_v3.py'):sftp.put(str(path),remote+'/scripts/'+path.name)
 sftp.put(str(ROOT/'scripts/start_v3_job.py'),remote+'/scripts/start_v3_job.py')
 sftp.put(str(ROOT/'config/step2_1b_v3/refined_mount.json'),remote+'/config/step2_1b_v3/refined_mount.json')
 for name in ['prepare_worker_v3','apply_refinement_v3','render_worker_v3']:
  info=json.loads(execute(shlex.quote(python)+' '+shlex.quote(remote+'/scripts/start_v3_job.py')+' '+name));deadline=time.monotonic()+1200
  while time.monotonic()<deadline:
   state=execute('ps -p '+str(info['pid'])+' -o stat= || true').strip()
   if not state or state.startswith('Z'):break
   print(name+': running',flush=True);time.sleep(5)
  else:raise TimeoutError(name+' exceeded deadline; inspect its project log')
  if name=='prepare_worker_v3':
   state=json.loads(execute('cat '+shlex.quote(remote+'/config/step2_1b_v3/final_placement.json')));assert state['fit_status']=='PASS',state
 state=json.loads(execute('cat '+shlex.quote(remote+'/outputs/step2_1b_v3/debug/render_status.json')));assert state['status']=='PASS',state
 for name in ['check_final_fit_v3','check_mount_connectivity_v3']:
  execute('cd '+shlex.quote(remote)+' && '+shlex.quote(python)+' '+shlex.quote('scripts/'+name+'.py'))
 def fetch(relative):
  path=remote+'/'+relative
  if stat.S_ISDIR(sftp.stat(path).st_mode):
   for name in sftp.listdir(path):
    if not name.endswith('.log'):fetch(relative+'/'+name)
  else:
   local=ROOT/relative;local.parent.mkdir(parents=True,exist_ok=True);sftp.get(path,str(local))
 for relative in ['config/step2_1b_v3','scenes/step2_1b_v3','outputs/step2_1b_v3/debug','reports/step2_1b_v3']:fetch(relative)
finally:client.close()
subprocess.run([sys.executable,str(ROOT/'scripts/build_fov_figure_v3.py')],cwd=ROOT,check=True)
print('Generated. Inspect PNG/PDF and fit views before updating visual-review status.')
