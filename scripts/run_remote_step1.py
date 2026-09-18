"""Upload this project, run Step 1, and fetch outputs. Never stores the password."""
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
    # Only source, derived settings, and referenced baseline USD are needed on the GPU.
    files=[]
    for folder in ('src','config','scripts'):
        files.extend(p for p in (root/folder).glob('*') if p.is_file() and p.name!='environment.local.json')
    files.extend([root/'scenes/rig_v0.2.usda',root/'assets/baseline/seven_camera_sim_layout_v01/models/seven_camera_rig.usda'])
    for path in files:
        dest=remote+'/'+path.relative_to(root).as_posix();mkdir(posixpath.dirname(dest));sftp.put(str(path),dest)
    print(f'Uploaded {len(files)} files to {remote}',flush=True)
    # Archive this project's previous result before a deliberate rerun.
    execute(f'cd {shlex.quote(remote)} && mkdir -p outputs reports && '
            'if [ -d outputs/step1 ]; then mv outputs/step1 outputs/step1_previous_$(date +%Y%m%d_%H%M%S); fi')
    job=json.loads(execute(shlex.quote(c['remote_python'])+' '+shlex.quote(remote+'/scripts/start_remote_job.py')+' --task all'))
    print('Started PID',job['pid'],flush=True)
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        status=execute(f'ps -p {int(job["pid"])} -o stat= || true').strip()
        if not status or status.startswith('Z'):break
        print('Step 1 rendering; log:',job['log'],flush=True);time.sleep(10)
    else:
        raise TimeoutError('Job still running after 15 minutes. Inspect reports/isaac_all.log; no other process was stopped.')
    def fetch(relative):
        path=remote+'/'+relative
        if stat.S_ISDIR(sftp.stat(path).st_mode):
            for name in sftp.listdir(path):fetch(relative+'/'+name)
        else:
            local=root/relative;local.parent.mkdir(parents=True,exist_ok=True);sftp.get(path,str(local))
    for relative in ('outputs/step1','scenes','reports/isaac_all.log','reports/current_job.json'):fetch(relative)
    status=json.loads((root/'outputs/step1/run_status.json').read_text())
    print(json.dumps(status,indent=2))
    if status['status']!='PASS':raise RuntimeError('Rendering finished with checks requiring review.')
finally:client.close()
