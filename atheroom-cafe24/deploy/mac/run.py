"""Personal Mac host: local data, subscription worker, authenticated Vercel tunnel.

Provision .local-cache/online/config.json locally. Never commit credentials.
Vercel CLI handles its own login/token refresh; this script never reads its tokens.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '.local-cache' / 'online'
STOP = False
CHILDREN = []


def stop(*_):
    global STOP
    STOP = True


def wait(seconds):
    until = time.monotonic() + seconds
    while not STOP and time.monotonic() < until:
        time.sleep(.25)


def launch(command, env, log_name):
    with (DATA / log_name).open('ab') as output:
        process = subprocess.Popen(command, cwd=ROOT / 'backend', env=env,
                                   stdout=output, stderr=output, start_new_session=True)
    CHILDREN.append(process)
    return process


def vc(config, endpoint, body=None):
    args = [config['npm'], 'exec', '--yes', '--package=vercel@59.15.1', '--', 'vercel',
            'api', endpoint, '--scope', config['scope'], '--global-config', config['vercel_auth'], '--raw']
    input_path = DATA / 'vercel-request.json'
    if body is not None:
        input_path.write_text(json.dumps(body))
        args += ['-X', 'POST', '--header', 'Content-Type: application/json', '--input', str(input_path)]
    try:
        result = subprocess.run(args, cwd=DATA, capture_output=True, text=True, timeout=120)
        if result.returncode:
            (DATA / 'vercel-error.log').write_text(result.stderr)
            raise RuntimeError('Vercel 연결 정보를 갱신하지 못했습니다. Vercel 로그인을 확인해주세요.')
        return json.loads(result.stdout)
    finally:
        input_path.unlink(missing_ok=True)


def connect_vercel(config, url):
    print('온라인 작업실에 맥북 연결을 반영하고 있습니다. 잠시 기다려주세요.', flush=True)
    for variable in [
        {'key': 'BACKEND_URL', 'value': url, 'type': 'encrypted', 'target': ['production']},
        {'key': 'STUDIO_BRIDGE_TOKEN', 'value': config['env']['BRIDGE_TOKEN'],
         'type': 'encrypted', 'target': ['production']}]:
        vc(config, f"/v10/projects/{config['project_id']}/env?upsert=true", variable)
    deployment = vc(config, '/v13/deployments', {
        'name': 'atheroom-cafe24', 'project': config['project_id'], 'target': 'production',
        'gitSource': {'type': 'github', 'repoId': config['repo_id'], 'ref': 'main'}})
    (DATA / 'deployment.json').write_text(json.dumps({'id': deployment['id'], 'url': deployment.get('url')}))
    for _ in range(120):
        if STOP: return
        state = vc(config, f"/v13/deployments/{deployment['id']}")
        if state.get('readyState') == 'READY':
            print('작업실 연결 완료: ' + config['url'], flush=True)
            print('이 창을 열어두세요. 맥북이 잠자기 상태이거나 인터넷이 끊기면 작업이 멈춥니다.', flush=True)
            subprocess.run(['open', config['url']], check=False)
            return
        if state.get('readyState') in ('ERROR', 'CANCELED'):
            raise RuntimeError('온라인 화면을 배포하지 못했습니다. Vercel 배포 상태를 확인해주세요.')
        wait(5)
    raise RuntimeError('연결 반영 시간이 길어지고 있습니다. 잠시 후 다시 실행해주세요.')


def main():
    os.umask(0o077)
    if not (DATA / 'config.json').exists():
        raise RuntimeError('이 맥의 온라인 작업실 연결 설정이 필요합니다.')
    guard = (DATA / 'launcher.lock').open('w')
    try:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('온라인 작업실 도우미가 이미 실행 중입니다. 기존 창을 확인해주세요.')
        return
    config = json.loads((DATA / 'config.json').read_text())
    env = os.environ.copy()
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL'):
        env.pop(key, None)
    env.update(config['env'])
    env.update(APP_ENV='mac', DEMO_MODE='false', AI_PROVIDER='codex', OPENAI_API_KEY='',
               STORAGE_BACKEND='local', EXECUTION_HOST='mac')
    env['BRIDGE_PUBLIC_URL_FILE']=str(DATA / 'tunnel-url')
    port = str(config.get('port', 8031))
    api = launch([config['python'], '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
                  '--port', port, '--no-access-log', '--no-proxy-headers'], env, 'api.log')
    for _ in range(60):
        if STOP: return
        if api.poll() is not None: raise RuntimeError('맥북 작업실을 시작하지 못했습니다. api.log를 확인해주세요.')
        try:
            request = urllib.request.Request('http://127.0.0.1:' + port + '/health',
                headers={'X-Studio-Bridge': env['BRIDGE_TOKEN']})
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200: break
        except OSError: wait(1)
    else: raise RuntimeError('맥북 작업실 시작 시간이 길어지고 있습니다.')
    worker = launch([config['python'], '-m', 'app.worker'], env, 'worker.log')
    tunnel = None
    while not STOP:
        if api.poll() is not None: raise RuntimeError('맥북 서버가 중단되었습니다. 다시 실행해주세요.')
        if worker.poll() is not None:
            print('작업 도우미를 다시 연결하고 있습니다.', flush=True)
            wait(5)
            if STOP: break
            worker = launch([config['python'], '-m', 'app.worker'], env, 'worker.log')
        if tunnel is None or tunnel.poll() is not None:
            log = DATA / 'tunnel.log'
            log.write_text('')
            tunnel = launch([config['cloudflared'], 'tunnel', '--url', 'http://127.0.0.1:' + port,
                             '--no-autoupdate', '--protocol', 'http2'], env, 'tunnel.log')
            for _ in range(90):
                if STOP: return
                match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log.read_text(errors='replace'))
                if match:
                    url = match.group(0)
                    (DATA / 'tunnel-url').write_text(url)
                    connect_vercel(config, url)
                    break
                if tunnel.poll() is not None: raise RuntimeError('맥북 외부 연결을 시작하지 못했습니다. 인터넷을 확인해주세요.')
                wait(1)
            else: raise RuntimeError('맥북 연결 주소를 받지 못했습니다. 인터넷을 확인해주세요.')
        wait(2)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        main()
    except Exception as exc:
        print(str(exc), flush=True)
        raise SystemExit(1)
    finally:
        # Stop the worker before the API/tunnel; allow an in-flight operation to finish.
        for process in reversed(CHILDREN):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in CHILDREN:
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL)
