import io
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from PIL import Image
from ..domain.contracts import PROFILES
from ..validators.files import inspect_image


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ComfyProvider:
    id = 'comfy-concept'
    capabilities = {'textToImage': True, 'imageToImage': True, 'imageTo3D': False, 'textTo3D': False,
                    'textureGeneration': False, 'rigging': False, 'animation': False, 'particles': False, 'shaderGeneration': False}

    def __init__(self, settings):
        self.settings = settings
        self.base = f'http://127.0.0.1:{settings.comfy_port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, payload=None, raw=None, content_type=None, limit=20*1024*1024):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Rota ComfyUI inválida.')
        body = json.dumps(payload).encode() if payload is not None else raw
        request = urllib.request.Request(self.base+path, data=body, headers={'Content-Type': content_type or 'application/json'})
        with self.opener.open(request, timeout=10) as response:
            data = response.read(limit+1)
        if len(data) > limit:
            raise ValueError('Resposta do motor excede limite.')
        return data

    def json(self, path, payload=None):
        return json.loads(self.request(path, payload))

    def status(self):
        result = {'id': self.id, 'name': 'ComfyUI · concept local', 'category': 'concept', 'status': 'not_configured', 'enabled': False,
                  'capabilities': self.capabilities, 'isLocal': True, 'isFree': True, 'requiresApiKey': False,
                  'requiresCredits': False, 'requiresSubscription': False, 'checkpoints': [], 'reason': 'ComfyUI não conectado.'}
        try:
            info = self.json('/object_info/CheckpointLoaderSimple')
            checkpoints = info['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
            result['checkpoints'] = checkpoints
            if self.settings.checkpoint not in checkpoints:
                result['reason'] = 'Selecione um checkpoint completo instalado no ComfyUI.'
            elif not self.settings.license_reviewed or not self.settings.model_license or not self.settings.model_version:
                result['reason'] = 'A licença e a versão do modelo precisam ser registradas antes de habilitar.'
            elif self.settings.model_license not in {'Apache-2.0', 'MIT', 'CC0-1.0'}:
                result['reason'] = 'Licença ainda não homologada para este provider. Use um modelo local compatível.'
            else:
                result.update(status='available', enabled=True, reason='Checkpoint local configurado; workflow de difusão padrão.')
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            pass
        return result

    def generate(self, payload, assets, cancelled, stage):
        status = self.status()
        if not status['enabled']:
            raise ValueError(status['reason'])
        profile = PROFILES[self.settings.profile]
        seed = payload['seed']
        prompt = payload['prompt']
        # Fixed built-in nodes only. No workflow or node code comes from the prompt/HTTP request.
        workflow = {
            '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': self.settings.checkpoint}},
            '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['1', 1]}},
            '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': '', 'clip': ['1', 1]}},
            '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': profile['width'], 'height': profile['height'], 'batch_size': 1}},
            '5': {'class_type': 'KSampler', 'inputs': {'seed': seed, 'steps': profile['steps'], 'cfg': 1.0, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0, 'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0], 'latent_image': ['4', 0]}},
            '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
            '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': 'FORGE/'+payload['request_id']}},
        }
        references = []
        for key in ('reference_id', 'sketch_id'):
            if payload.get(key):
                asset = assets.get(payload[key])
                if asset['project_id'] != payload['project_id'] or asset['kind'] not in {'reference', 'sketch', 'concept'}:
                    raise ValueError('Referência inválida para este projeto.')
                references.append(assets.storage.read(asset['version']['blob']))
        if references:
            # Composite actual supplied inputs locally, preserving original blobs separately.
            image = Image.open(io.BytesIO(references[0])).convert('RGB').resize((profile['width'], profile['height']))
            if len(references) == 2:
                overlay = Image.open(io.BytesIO(references[1])).convert('RGB').resize(image.size)
                image = Image.blend(image, overlay, .35)
            output = io.BytesIO()
            image.save(output, format='PNG')
            boundary = 'forge'+secrets.token_hex(12)
            filename = 'forge-'+payload['request_id']+'.png'
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n').encode()+output.getvalue()+f'\r\n--{boundary}--\r\n'.encode()
            upload = json.loads(self.request('/upload/image', raw=body, content_type='multipart/form-data; boundary='+boundary))
            workflow['8'] = {'class_type': 'LoadImage', 'inputs': {'image': upload['name']}}
            workflow['4'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['8', 0], 'vae': ['1', 2]}}
            workflow['5']['inputs']['denoise'] = .75
        if cancelled():
            raise InterruptedError('Cancelado antes da geração.')
        receipt = self.json('/prompt', {'prompt': workflow, 'client_id': 'forge-'+payload['request_id']})
        remote_id = receipt['prompt_id']
        stage('processing', 'Gerando concept no ComfyUI')
        deadline = time.monotonic()+1800
        try:
            while time.monotonic() < deadline:
                if cancelled():
                    # Queue removal is scoped. Never interrupt unrelated GPU jobs globally.
                    self.json('/queue', {'delete': [remote_id]})
                    raise InterruptedError('Cancelado no FORGE. Uma execução já iniciada no ComfyUI pode terminar; seu resultado será descartado.')
                history = self.json('/history/'+urllib.parse.quote(remote_id, safe=''))
                if remote_id in history:
                    item = history[remote_id]
                    if item.get('status', {}).get('status_str') == 'error':
                        raise ValueError('O ComfyUI não conseguiu executar o modelo. Consulte os logs locais do motor.')
                    images = item.get('outputs', {}).get('7', {}).get('images', [])
                    if images:
                        record = images[0]
                        if record.get('type') != 'output' or '..' in record.get('subfolder', '').split('/') or '/' in record['filename'] or '\\' in record['filename']:
                            raise ValueError('Motor retornou um caminho de imagem inesperado.')
                        stage('post_processing', 'Validando imagem gerada')
                        content = self.request('/view?'+urllib.parse.urlencode({k: record.get(k, '') for k in ('filename', 'subfolder', 'type')}))
                        inspect_image(content)
                        return content, {'source': 'Generated', 'provider': self.id, 'provider_version': '1.0.0', 'model': self.settings.checkpoint,
                                         'model_version': self.settings.model_version, 'license': self.settings.model_license, 'prompt': prompt,
                                         'seed': seed, 'references': [payload.get('reference_id'), payload.get('sketch_id')], 'configuration': profile,
                                         'comfy_prompt_id': remote_id}
                time.sleep(2)
            raise TimeoutError('O motor excedeu o limite de 30 minutos. Verifique o ComfyUI antes de tentar novamente.')
        finally:
            if profile['unload']:
                try:
                    queue = self.json('/queue')
                    if not queue.get('queue_running') and not queue.get('queue_pending'):
                        self.json('/free', {'unload_models': True, 'free_memory': True})
                except (OSError, ValueError):
                    pass
