"""Project-scoped SFTP and command session. Password is kept only in memory."""
import getpass
import json
import posixpath
from pathlib import Path
import sys
import paramiko

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / 'config/environment.local.json').read_text())
REMOTE = config['remote_project']
client = paramiko.SSHClient()
known = ROOT / '.ssh/known_hosts'
known.parent.mkdir(exist_ok=True)
if known.exists():
    client.load_host_keys(str(known))
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(config['ssh_host'], port=config['ssh_port'], username=config['ssh_user'],
               password=getpass.getpass('SSH password: '), look_for_keys=False, allow_agent=False, timeout=20)
client.save_host_keys(str(known))
sftp = client.open_sftp()

def mkdir(path):
    try:
        sftp.stat(path)
    except FileNotFoundError:
        mkdir(posixpath.dirname(path))
        sftp.mkdir(path)

def remote_path(relative):
    target = posixpath.normpath(REMOTE + '/' + relative.replace('\\', '/'))
    if not target.startswith(REMOTE + '/'):
        raise ValueError('Remote path outside project')
    return target

def local_path(relative):
    target = (ROOT / relative).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError('Local path outside project')
    return target

print('READY', flush=True)
for line in sys.stdin:
    try:
        req = json.loads(line)
        if req['op'] == 'exec':
            _, out, err = client.exec_command(req['command'], timeout=req.get('timeout', 300))
            stdout = out.read().decode('utf-8', errors='replace')
            stderr = err.read().decode('utf-8', errors='replace')
            code = out.channel.recv_exit_status()
            if req.get('log'):
                local_path(req['log']).write_text(stdout + '\n' + stderr, encoding='utf-8')
            print(json.dumps({'exit_code': code, 'stdout': stdout[-req.get('tail',20000):], 'stderr': stderr[-4000:]}), flush=True)
        elif req['op'] == 'put':
            count = 0
            for relative in req['paths']:
                source = local_path(relative)
                paths = source.rglob('*') if source.is_dir() else [source]
                for path in paths:
                    if not path.is_file() or '__pycache__' in path.parts:
                        continue
                    dest = remote_path(path.relative_to(ROOT).as_posix())
                    mkdir(posixpath.dirname(dest))
                    sftp.put(str(path), dest)
                    count += 1
            print(json.dumps({'uploaded': count, 'root': REMOTE}), flush=True)
        elif req['op'] == 'get':
            def fetch(relative):
                import stat
                rp = remote_path(relative)
                if stat.S_ISDIR(sftp.stat(rp).st_mode):
                    for name in sftp.listdir(rp):
                        fetch(relative + '/' + name)
                else:
                    lp = local_path(relative)
                    lp.parent.mkdir(parents=True, exist_ok=True)
                    sftp.get(rp, str(lp))
            for relative in req['paths']:
                fetch(relative)
            print('DOWNLOADED', flush=True)
        elif req['op'] == 'close':
            break
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), flush=True)
    print('READY', flush=True)
client.close()
