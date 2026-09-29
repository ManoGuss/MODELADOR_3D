import uuid
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
