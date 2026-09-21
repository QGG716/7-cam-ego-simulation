"""Reproduce v6 using the configured GPU project; password stays in memory."""
import getpass,json,shlex,time,stat,subprocess,sys
from pathlib import Path
import paramiko
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'scripts/build_optics_v6.py')],check=True,cwd=ROOT)
cfg=json.loads((ROOT/'config/environment.local.json').read_text());remote=cfg['remote_project'];python=cfg['remote_python'];client=paramiko.SSHClient();client.load_host_keys(str(ROOT/'.ssh/known_hosts'));client.set_missing_host_key_policy(paramiko.RejectPolicy());client.connect(cfg['ssh_host'],port=cfg['ssh_port'],username=cfg['ssh_user'],password=getpass.getpass('SSH password: '),look_for_keys=False,allow_agent=False,timeout=20)
def execute(command):
 _,out,err=client.exec_command(command,timeout=300);text=out.read().decode();error=err.read().decode();code=out.channel.recv_exit_status()
 if code:raise RuntimeError(error or text)
 return text
try:
 sftp=client.open_sftp()
 execute('mkdir -p '+shlex.quote(remote+'/config/step2_1b_v6')+' '+shlex.quote(remote+'/scenes/step2_1b_v6'))
 paths=['config/rig_sim_v0.2.json','src/rig_common.py','src/projection.py','config/step2_1b_v6/derived_calibration.json','config/step2_1b_v6/final_placement.json','scenes/step2_1b_v6/indoor_worker.usda','scripts/build_lut_v6.py','scripts/render_worker_v6.py','scripts/start_v6_job.py']
 for p in paths:sftp.put(str(ROOT/p),remote+'/'+p)
 for name in ['build_lut_v6','render_worker_v6']:
  result=json.loads(execute(shlex.quote(python)+' '+shlex.quote(remote+'/scripts/start_v6_job.py')+' '+name));deadline=time.monotonic()+1200
  while time.monotonic()<deadline:
   state=execute('ps -p '+str(result['pid'])+' -o stat= || true').strip()
   if not state or state.startswith('Z'):break
   print(name+': running',flush=True);time.sleep(5)
  else:raise TimeoutError(name)
  if name=='build_lut_v6':assert len(json.loads(execute('cat '+shlex.quote(remote+'/config/step2_1b_v6/lut/manifest.json')))['records'])==4
 status=json.loads(execute('cat '+shlex.quote(remote+'/reports/step2_1b_v6/render_status.json')));assert status['status']=='PASS',status
 def fetch(relative):
  rp=remote+'/'+relative
  if stat.S_ISDIR(sftp.stat(rp).st_mode):
   for child in sftp.listdir(rp):fetch(relative+'/'+child)
  else:
   local=ROOT/relative;local.parent.mkdir(parents=True,exist_ok=True);sftp.get(rp,str(local))
 for relative in ['config/step2_1b_v6/lut','outputs/step2_1b_v6/raw','reports/step2_1b_v6']:fetch(relative)
finally:client.close()
subprocess.run([sys.executable,str(ROOT/'scripts/build_fov_figure_v6.py')],check=True,cwd=ROOT)
print('Inspect final PNG/PDF before refreshing visual-review metadata.')
