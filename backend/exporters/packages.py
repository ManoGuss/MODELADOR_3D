import hashlib
import io
import json
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath
from uuid import UUID
from ..validators.files import parse_glb

PREFIXES = {'static_mesh': 'SM', 'skeletal_mesh': 'SK', 'material': 'M', 'material_instance': 'MI',
            'texture': 'T', 'animation': 'A', 'vfx': 'VFX', 'particles': 'PS', 'audio': 'S'}


def technical_name(name, kind):
    if kind not in PREFIXES:
        raise ValueError('Tipo de asset sem convenção de exportação.')
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    ascii_name = re.sub(r'[^A-Za-z0-9_]+', '_', ascii_name).strip('_')[:64] or 'Asset'
    return f'{PREFIXES[kind]}_{ascii_name}'


def safe_member(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or name.startswith('/') or any(p in {'..', '.'} for p in name.split('/')) or path.suffix.lower() not in {'.glb', '.fbx', '.png', '.jpg', '.webp', '.wav', '.json', '.txt'}:
        raise ValueError('Caminho ou extensão não permitidos no pacote.')
    if len(name) > 240 or any(ord(c) < 32 for c in name):
        raise ValueError('Nome inválido no pacote.')
    return name


def build_package(files, manifest):
    manifest = dict(manifest)
    manifest['files'] = [{'path': safe_member(path), 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)} for path, data in sorted(files.items())]
    if 'forge_manifest.json' in files:
        raise ValueError('Manifest duplicado.')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
        archive.writestr('forge_manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    content = output.getvalue()
    validate_package(content)
    return content, manifest


def validate_package(content, max_uncompressed=512*1024*1024):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > 4096 or sum(info.file_size for info in infos) > max_uncompressed:
                raise ValueError('Pacote excede limites de arquivos/tamanho.')
            names = [safe_member(info.filename) for info in infos]
            if len(names) != len(set(n.casefold() for n in names)):
                raise ValueError('Arquivos duplicados no ZIP.')
            if any((info.external_attr >> 16) & 0o170000 == 0o120000 or info.flag_bits & 1 for info in infos):
                raise ValueError('Links simbólicos e ZIP criptografado não permitidos.')
            if 'forge_manifest.json' not in names or archive.getinfo('forge_manifest.json').file_size > 4*1024*1024:
                raise ValueError('Manifest ausente ou grande demais.')
            manifest = json.loads(archive.read('forge_manifest.json'))
            if manifest.get('schemaVersion') != 1:
                raise ValueError('Versão do manifest incompatível.')
            UUID(manifest['projectId'])
            if manifest.get('assetId'):
                UUID(manifest['assetId'])
            expected = {entry['path']: entry for entry in manifest['files']}
            if len(expected) != len(manifest['files']) or set(names) != set(expected) | {'forge_manifest.json'}:
                raise ValueError('ZIP contém arquivos não previstos no manifest.')
            for path, entry in expected.items():
                safe_member(path)
                data = archive.read(path)
                if len(data) != entry['size'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                    raise ValueError('Arquivo corrompido ou hash inválido.')
            return manifest
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Pacote ou manifest inválido.') from error


def asset_package(asset, data):
    metadata = asset['version']['metadata']
    kind = asset['kind']
    files = {}
    extension = asset['version']['blob'].split('.')[-1]
    name = technical_name(asset['name'], kind) if kind in PREFIXES else 'Asset'
    files[f'model/{name}.{extension}'] = data
    materials, textures = [], []
    if extension == 'glb':
        document, binary = parse_glb(data)
        for index, image in enumerate(document.get('images', [])):
            view = document['bufferViews'][image['bufferView']]
            ext = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}[image['mimeType']]
            path = f'textures/T_{name}_{index}.{ext}'
            files[path] = binary[view.get('byteOffset', 0):view.get('byteOffset', 0)+view['byteLength']]
            textures.append({'imageIndex': index, 'path': path})
        for index, material in enumerate(document.get('materials', [])):
            pbr = material.get('pbrMetallicRoughness', {})
            maps = {}
            for role, info, channel in [('BaseColor', pbr.get('baseColorTexture'), 'rgba'), ('Normal', material.get('normalTexture'), 'rgb'), ('Roughness', pbr.get('metallicRoughnessTexture'), 'g'), ('Metallic', pbr.get('metallicRoughnessTexture'), 'b'), ('AO', material.get('occlusionTexture'), 'r'), ('Emission', material.get('emissiveTexture'), 'rgb')]:
                if info:
                    image_index = document['textures'][info['index']]['source']
                    maps[role] = {'path': textures[image_index]['path'], 'channel': channel, 'colorSpace': 'sRGB' if role in {'BaseColor', 'Emission'} else 'linear'}
            materials.append({'index': index, 'name': technical_name(material.get('name', f'{name}_{index}'), 'material'), 'maps': maps, 'definition': material})
    # Attribution is provenance, never a claim of ownership of imported/generated assets.
    provenance = metadata.get('provenance', {})
    files['LICENSES.txt'] = ('Origem: '+str(provenance.get('source', asset['source']))+'\nLicença do conteúdo: '+str(provenance.get('license', 'Não declarada pelo fornecedor.'))+'\nFORGE não reivindica propriedade deste conteúdo.\n').encode()
    manifest = {'schemaVersion': 1, 'forgeVersion': '0.2.0', 'projectId': asset['project_id'], 'assetId': asset['id'],
                'assetName': name, 'assetType': kind, 'version': asset['version']['number'], 'versionId': asset['version']['id'],
                'unit': 'meter', 'engineTarget': 'generic', 'exportProfileVersion': '1.0.0',
                'exports': {extension: f'model/{name}.{extension}'}, 'materials': materials, 'textures': textures,
                'animations': metadata.get('animations', []), 'provenance': provenance, 'warnings': metadata.get('warnings', [])}
    if kind == 'particles':
        manifest['warnings'] = ['Definição de partículas exportada. Conversão Niagara não implementada.']
    return build_package(files, manifest)
