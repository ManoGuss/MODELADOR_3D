import uuid
import json
import struct
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        yield client


def test_project_round_trip_and_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/projects').json() == []
        response = client.post('/api/projects', json={'name': 'Floresta São João'})
        assert response.status_code == 201
        project = response.json()
        assert (tmp_path / 'projects' / project['id'] / 'assets').is_dir()
        workspace = project['workspace'] | {'grid': False, 'camera': [4, 5, 6]}
        payload = {'name': 'Renomeado', 'revision': 0, 'workspace': workspace}
        saved = client.put('/api/projects/' + project['id'], json=payload)
        assert saved.status_code == 200
        assert saved.json()['revision'] == 1
        assert client.put('/api/projects/' + project['id'], json=payload).status_code == 409
    with TestClient(create_app(tmp_path)) as restarted:
        restored = restarted.get('/api/projects/' + project['id']).json()
        assert restored['workspace'] == workspace
        assert restored['name'] == 'Renomeado'


@pytest.mark.parametrize('name', ['', '   ', 'a' * 101, 'a\x00b'])
def test_invalid_name(client, name):
    assert client.post('/api/projects', json={'name': name}).status_code == 422


def test_path_and_missing(client):
    assert client.get('/api/projects/not-a-uuid').status_code == 422
    assert client.get('/api/projects/' + str(uuid.uuid4())).status_code == 404
    assert client.get('/api/unknown').status_code == 404
    assert client.post('/api/projects', json={'name': 'safe', 'path': '../../outside'}).status_code == 422


def test_local_security(client):
    assert client.post('/api/projects', json={'name': 'x'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/projects', headers={'Host': 'evil.example'}).status_code == 400
    assert client.post('/api/projects', content='{}').status_code == 415
    assert client.post('/api/projects', json={'name': 'a' * 40000}).status_code == 413
    assert client.get('/api/health', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403


def test_health_and_providers(client):
    assert client.get('/api/health').json()['local_only'] is True
    assert all(not p['enabled'] and p['status'] == 'not_configured' for p in client.get('/api/providers').json())


def test_diagnostics_real(client):
    result = client.get('/api/diagnostics')
    assert result.status_code == 200
    assert result.json()['ram_bytes'] > 0
    assert result.json()['free_bytes'] > 0


def test_invalid_coordinate(client):
    project = client.post('/api/projects', json={'name': 'Teste'}).json()
    payload = {'name': 'Teste', 'revision': 0, 'workspace': project['workspace'] | {'camera': [1e200, 0, 0]}}
    assert client.put('/api/projects/' + project['id'], json=payload).status_code == 422


def minimal_glb():
    document = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': 36}],
                'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 36}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0,0,0], 'max': [1,1,0]}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}], 'nodes': [{'mesh': 0}]}
    blob = struct.pack('<9f', 0,0,0, 1,0,0, 0,1,0)
    payload = json.dumps(document, separators=(',', ':')).encode()
    payload += b' ' * ((4-len(payload)%4)%4)
    return struct.pack('<4sII', b'glTF', 2, 12+8+len(payload)+8+len(blob)) + struct.pack('<II', len(payload), 0x4e4f534a) + payload + struct.pack('<II', len(blob), 0x004e4942) + blob


def test_real_glb_import_version_graph_and_export(client):
    project = client.post('/api/projects', json={'name': 'Assets'}).json()
    response = client.post('/api/projects/'+project['id']+'/assets/import?name=Triangulo&category=model', content=minimal_glb(), headers={'Content-Type': 'application/octet-stream'})
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset['kind'] == 'static_mesh'
    assert asset['version']['metadata']['vertices'] == 3
    assert client.get('/api/projects/'+project['id']+'/assets').json()[0]['id'] == asset['id']
    duplicate = client.post('/api/assets/'+asset['id']+'/variants')
    assert duplicate.status_code == 201
    exported = client.post('/api/assets/'+asset['id']+'/export', json={'format': 'zip'})
    assert exported.status_code == 202
    job = exported.json()
    # Export worker is asynchronous; poll briefly, never report a queued job as done.
    import time
    for _ in range(30):
        state = client.get('/api/jobs/'+job['id']).json()
        if state['status'] in {'completed', 'failed'}:
            break
        time.sleep(.05)
    assert state['status'] == 'completed', state
    package = client.get(state['result']['url'])
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert 'forge_manifest.json' in archive.namelist()
        assert json.loads(archive.read('forge_manifest.json'))['assetId'] == asset['id']


def test_settings_and_profiles_are_explicit(client):
    settings = client.get('/api/settings')
    assert settings.status_code == 200
    assert settings.json()['profiles']['low_vram']['unload'] is True
    updated = client.put('/api/settings', json={'profile': 'balanced', 'target_engine': 'unreal', 'comfy_port': 8188, 'checkpoint': '', 'model_license': '', 'model_version': '', 'license_reviewed': False})
    assert updated.status_code == 200
    assert updated.json()['profile'] == 'balanced'
    assert all(item['status'] in {'not_configured', 'available'} for item in client.get('/api/providers').json())
