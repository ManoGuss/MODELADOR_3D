import platform
import shutil
import subprocess
import sys
import urllib.request
import psutil


def diagnostics(root):
    gpu = {'status': 'Não detectado', 'devices': [], 'reason': None}
    executable = shutil.which('nvidia-smi')
    if executable:
        try:
            result = subprocess.run([executable, '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5, check=True)
            gpu = {'status': 'Detectado', 'devices': [dict(zip(('name', 'vram_mb', 'driver'), [v.strip() for v in line.split(',')])) for line in result.stdout.strip().splitlines()], 'reason': None}
        except (OSError, subprocess.SubprocessError) as error:
            gpu['reason'] = str(error)
    comfy = 'Não detectado'
    try:
        # Explicit loopback only, no proxies and no redirects to third parties.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open('http://127.0.0.1:8188/system_stats', timeout=1) as response:
            import json
            body = json.loads(response.read(65536))
            comfy = 'Detectado' if 'system' in body and 'devices' in body else 'Resposta incompatível'
    except Exception:
        pass
    memory = psutil.virtual_memory()
    return {'os': platform.platform(), 'cpu': platform.processor() or 'Não identificado',
            'cores': psutil.cpu_count(), 'ram_bytes': memory.total, 'ram_available_bytes': memory.available,
            'gpu': gpu, 'python': sys.version.split()[0], 'blender': shutil.which('blender'),
            'comfyui': comfy, 'storage': str(root), 'free_bytes': shutil.disk_usage(root).free,
            'cuda': 'Driver NVIDIA detectado; runtime de inferência não verificado' if gpu['devices'] else 'Não verificado',
            'rocm': 'Não verificado'}
