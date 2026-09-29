import io
import json
import math
import struct
import wave
from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 16_000_000
MAX_FILE = 128 * 1024 * 1024


def parse_glb(data):
    if len(data) < 20 or len(data) > MAX_FILE:
        raise ValueError('GLB vazio, incompleto ou maior que 128 MB.')
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('Cabeçalho GLB 2.0 inválido.')
    chunks, offset = [], 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError('Chunk GLB truncado.')
        size, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        if size % 4 or offset + size > len(data):
            raise ValueError('Tamanho de chunk GLB inválido.')
        chunks.append((kind, data[offset:offset+size]))
        offset += size
    if not chunks or chunks[0][0] != 0x4E4F534A or len(chunks) > 2:
        raise ValueError('GLB deve conter JSON e um buffer binário.')
    document = json.loads(chunks[0][1], parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Número não finito')))
    if document.get('asset', {}).get('version') != '2.0':
        raise ValueError('Versão glTF incompatível.')
    binary = chunks[1][1] if len(chunks) == 2 and chunks[1][0] == 0x004E4942 else b''
    buffers = document.get('buffers', [])
    if len(buffers) != 1 or buffers[0].get('uri') or buffers[0].get('byteLength', len(binary)+1) > len(binary):
        raise ValueError('Use GLB autocontido: buffers externos não são permitidos.')
    if any(image.get('uri') for image in document.get('images', [])):
        raise ValueError('Texturas precisam estar incorporadas ao GLB; URLs e paths externos são bloqueados.')
    supported = {'KHR_materials_unlit', 'KHR_materials_clearcoat', 'KHR_materials_emissive_strength',
                 'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_transmission',
                 'KHR_materials_volume', 'KHR_texture_transform', 'KHR_materials_sheen',
                 'KHR_materials_iridescence', 'KHR_materials_anisotropy'}
    if set(document.get('extensionsRequired', [])) - supported:
        raise ValueError('GLB contém extensão obrigatória ainda não suportada. Exporte sem compressão Draco/KTX.')
    def check_external(value):
        if isinstance(value, dict):
            if 'uri' in value:
                raise ValueError('Referências externas no GLB não são permitidas.')
            for child in value.values():
                check_external(child)
        elif isinstance(value, list):
            for child in value:
                check_external(child)
    check_external(document)
    for view in document.get('bufferViews', []):
        start, size = view.get('byteOffset', 0), view.get('byteLength', 0)
        if view.get('buffer') != 0 or start < 0 or size < 0 or start + size > len(binary):
            raise ValueError('Buffer de geometria/textura fora dos limites.')
    return document, binary


def inspect_glb(data):
    document, binary = parse_glb(data)
    accessors = document.get('accessors', [])
    nodes = document.get('nodes', [])
    meshes = document.get('meshes', [])
    checks, warnings = [], []
    if not meshes:
        raise ValueError('O arquivo não contém uma mesh.')
    if len(nodes) > 20000 or len(accessors) > 20000:
        raise ValueError('Cena excede os limites de complexidade.')
    visiting, visited = set(), set()
    def visit(index):
        if not isinstance(index, int) or not 0 <= index < len(nodes) or index in visiting:
            raise ValueError('Hierarquia de nós inválida ou cíclica.')
        if index in visited:
            return
        visiting.add(index)
        node = nodes[index]
        for key, size in [('translation', 3), ('rotation', 4), ('scale', 3), ('matrix', 16)]:
            if key in node and (len(node[key]) != size or any(not math.isfinite(x) for x in node[key])):
                raise ValueError('Transformação inválida.')
        if 'mesh' in node and not 0 <= node['mesh'] < len(meshes):
            raise ValueError('Mesh referenciada não existe.')
        for child in node.get('children', []):
            visit(child)
        visiting.remove(index)
        visited.add(index)
    try:
        for index in range(len(nodes)):
            visit(index)
    except RecursionError as error:
        raise ValueError('Hierarquia excessivamente profunda.') from error

    formats = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
    counts = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
    def values(index):
        if not isinstance(index, int) or not 0 <= index < len(accessors):
            raise ValueError('Accessor inexistente.')
        a = accessors[index]
        if 'sparse' in a:
            raise ValueError('Accessors sparse ainda não suportados pela validação. Exporte sem sparse.')
        if a.get('componentType') not in formats or a.get('type') not in counts:
            raise ValueError('Tipo de accessor inválido/não suportado.')
        views = document.get('bufferViews', [])
        if not isinstance(a.get('bufferView'), int) or not 0 <= a['bufferView'] < len(views):
            raise ValueError('Accessor sem buffer válido.')
        view = views[a['bufferView']]
        fmt, width = formats[a['componentType']]
        count = a.get('count', 0)
        components = counts[a['type']]
        stride = view.get('byteStride', width*components)
        start = a.get('byteOffset', 0)
        if count < 1 or count > 2_000_000 or start < 0 or stride < width*components or start + (count-1)*stride + width*components > view['byteLength']:
            raise ValueError('Accessor fora dos limites ou grande demais.')
        return [struct.unpack_from('<'+fmt*components, binary, view.get('byteOffset', 0)+start+i*stride) for i in range(count)]

    vertices, triangles, degenerate = 0, 0, 0
    has_normals = has_uv = True
    for mesh in meshes:
        for primitive in mesh.get('primitives', []):
            if primitive.get('mode', 4) != 4:
                raise ValueError('Somente meshes de triângulos são suportadas.')
            attrs = primitive.get('attributes', {})
            if 'POSITION' not in attrs:
                raise ValueError('Mesh sem posições de vértices.')
            positions = values(attrs['POSITION'])
            if any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in positions):
                raise ValueError('Geometria contém posições inválidas.')
            vertices += len(positions)
            if vertices > 2_000_000:
                raise ValueError('Limite de dois milhões de vértices excedido.')
            indices = [i[0] for i in values(primitive['indices'])] if 'indices' in primitive else list(range(len(positions)))
            if len(indices) % 3 or any(not isinstance(i, int) or not 0 <= i < len(positions) for i in indices):
                raise ValueError('Índices de triângulos inválidos.')
            triangles += len(indices)//3
            for i in range(0, len(indices), 3):
                a, b, c = (positions[indices[i+j]] for j in range(3))
                u = [b[j]-a[j] for j in range(3)]
                v = [c[j]-a[j] for j in range(3)]
                cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
                degenerate += sum(x*x for x in cross) < 1e-20
            has_normals &= 'NORMAL' in attrs
            has_uv &= 'TEXCOORD_0' in attrs
            for attr in ('NORMAL', 'TEXCOORD_0', 'WEIGHTS_0', 'JOINTS_0'):
                if attr in attrs:
                    entries = values(attrs[attr])
                    if len(entries) != len(positions) or any(not math.isfinite(v) for e in entries for v in e):
                        raise ValueError(f'{attr} inválido.')
            if 'material' in primitive and not 0 <= primitive['material'] < len(document.get('materials', [])):
                raise ValueError('Material referenciado não existe.')
    if not vertices or not triangles:
        raise ValueError('Geometria vazia.')
    for skin in document.get('skins', []):
        if not skin.get('joints') or any(not 0 <= i < len(nodes) for i in skin['joints']):
            raise ValueError('Skeleton inválido.')
        if 'inverseBindMatrices' in skin and len(values(skin['inverseBindMatrices'])) != len(skin['joints']):
            raise ValueError('Bind pose incompatível com skeleton.')
    animations = []
    for index, animation in enumerate(document.get('animations', [])):
        duration = 0
        for sampler in animation.get('samplers', []):
            times = values(sampler['input'])
            if any(len(t) != 1 or not math.isfinite(t[0]) or t[0] < 0 for t in times) or any(a[0] >= b[0] for a, b in zip(times, times[1:])):
                raise ValueError('Tempos de animação inválidos.')
            values(sampler['output'])
            duration = max(duration, times[-1][0])
        for channel in animation.get('channels', []):
            if not 0 <= channel['sampler'] < len(animation.get('samplers', [])) or not 0 <= channel.get('target', {}).get('node', -1) < len(nodes):
                raise ValueError('Canal de animação inválido.')
        animations.append({'name': animation.get('name', f'Clip {index+1}'), 'duration': duration})
    for image in document.get('images', []):
        view_id = image.get('bufferView', -1)
        if not 0 <= view_id < len(document.get('bufferViews', [])):
            raise ValueError('Textura sem buffer incorporado.')
        view = document['bufferViews'][view_id]
        inspect_image(binary[view.get('byteOffset', 0):view.get('byteOffset', 0)+view['byteLength']])
    for texture in document.get('textures', []):
        if not 0 <= texture.get('source', -1) < len(document.get('images', [])):
            raise ValueError('Textura referencia imagem ausente.')
    if degenerate:
        warnings.append(f'{degenerate} faces degeneradas; corrija antes de usar em produção.')
    if not has_normals:
        warnings.append('Normais ausentes.')
    if not has_uv:
        warnings.append('UV ausente.')
    warnings += ['LOD e collision não certificados.', 'Escala em metros; confirme dimensões antes de exportar.', 'T-pose e qualidade de deformação não verificadas.'] if document.get('skins') else ['LOD e collision não certificados.', 'Escala em metros; confirme dimensões antes de exportar.']
    checks = {'mesh': True, 'normals': has_normals, 'uv': has_uv, 'materials': bool(document.get('materials')), 'textures': bool(document.get('images')), 'skeleton': bool(document.get('skins')), 'animations': bool(animations), 'integrity': True}
    return {'kind': 'skeletal_mesh' if document.get('skins') else 'static_mesh', 'vertices': vertices, 'triangles': triangles, 'degenerate_faces': degenerate,
            'checks': checks, 'warnings': warnings, 'animations': animations, 'materials': document.get('materials', []),
            'graph': {key: len(document.get(key, [])) for key in ('meshes', 'materials', 'textures', 'skins', 'animations', 'nodes')}, 'unit': 'meter'}


def inspect_image(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError('Use PNG/JPG/WEBP até 16 megapixels.')
            metadata = {'width': image.width, 'height': image.height, 'extension': {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[image.format]}
            image.verify()
        return metadata
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError('Imagem inválida ou grande demais.') from error


def inspect_audio(data):
    try:
        with wave.open(io.BytesIO(data)) as audio:
            if audio.getnchannels() > 2 or audio.getsampwidth() not in {1, 2, 3, 4} or not audio.getframerate():
                raise ValueError('Use WAV PCM mono ou estéreo.')
            if len(audio.readframes(audio.getnframes())) != audio.getnframes()*audio.getnchannels()*audio.getsampwidth():
                raise ValueError('WAV truncado.')
            return {'duration': audio.getnframes()/audio.getframerate(), 'sample_rate': audio.getframerate()}
    except (wave.Error, EOFError) as error:
        raise ValueError('WAV inválido; use PCM.') from error
