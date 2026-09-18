"""Upload this project, run Step 2, and fetch outputs. Never stores the password."""
import getpass,json,posixpath,shlex,stat,time
from pathlib import Path
import paramiko

root=Path(__file__).resolve().parents[1]
c=json.loads((root/'config/environment.local.json').read_text())
remote=c['remote_project']
if remote!='/root/autodl-tmp/7-cam-ego-simulation-step1':
    raise RuntimeError('Review remote project path before changing the dedicated target.')
client=paramiko.SSHClient()
known=root/'.ssh/known_hosts';known.parent.mkdir(exist_ok=True)
if known.exists():client.load_host_keys(str(known))
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(c['ssh_host'],port=c['ssh_port'],username=c['ssh_user'],password=getpass.getpass('SSH password: '),
               allow_agent=False,look_for_keys=False,timeout=20)
client.save_host_keys(str(known))

def execute(command):
    _,out,err=client.exec_command(command,timeout=120)
    text=out.read().decode();error=err.read().decode()
    if out.channel.recv_exit_status():raise RuntimeError(error or text)
    return text

try:
    sftp=client.open_sftp()
    def mkdir(path):
        try:sftp.stat(path)
        except FileNotFoundError:
            mkdir(posixpath.dirname(path));sftp.mkdir(path)
    # Frozen inputs must already exist and match; never overwrite Step 1 inputs remotely.
    import hashlib
    frozen=['config/rig_sim_v0.2.json','src/rig_common.py','src/projection.py','scenes/rig_v0.2.usda','scenes/inspection_scene.usda','assets/baseline/seven_camera_sim_layout_v01/models/seven_camera_rig.usda']
    for relative in frozen:
        with sftp.open(remote+'/'+relative,'rb') as stream:actual=hashlib.sha256(stream.read()).hexdigest()
        assert actual==hashlib.sha256((root/relative).read_bytes()).hexdigest(),relative
    for relative in ['scripts/isaac_step2.py','scripts/analyze_step2.py','scripts/start_step2_job.py','config/step2_analysis.json']:
        dest=remote+'/'+relative;mkdir(posixpath.dirname(dest));sftp.put(str(root/relative),dest)
    job=json.loads(execute(shlex.quote(c['remote_python'])+' '+shlex.quote(remote+'/scripts/start_step2_job.py')))
    print('Started PID',job['pid'],flush=True)
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        status=execute(f'ps -p {int(job["pid"])} -o stat= || true').strip()
        if not status or status.startswith('Z'):break
        print('Step 2 rendering; log:','reports/step2/isaac_step2.log',flush=True);time.sleep(10)
    else:
        raise TimeoutError('Job still running after 15 minutes. Inspect reports/step2/isaac_step2.log; no other process was stopped.')
    def fetch(relative):
        path=remote+'/'+relative
        if stat.S_ISDIR(sftp.stat(path).st_mode):
            for name in sftp.listdir(path):fetch(relative+'/'+name)
        else:
            local=root/relative;local.parent.mkdir(parents=True,exist_ok=True);sftp.get(path,str(local))
    for relative in ('outputs/step2','scenes/step2','reports/step2/isaac_step2.log'):fetch(relative)
    status=json.loads((root/'outputs/step2/render_status.json').read_text())
    print(json.dumps(status,indent=2))
    if status['status']!='PASS':raise RuntimeError('Rendering finished with checks requiring review.')
finally:client.close()
