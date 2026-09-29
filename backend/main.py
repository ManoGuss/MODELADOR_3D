import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .database import Database
from .diagnostics import diagnostics


class Workspace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    grid: bool = True
    environment: bool = True
    overlays: bool = True
    camera: list[float] = Field(default_factory=lambda: [12, 4, 12], min_length=3, max_length=3)
    target: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)

    @field_validator('camera', 'target')
    @classmethod
    def finite(cls, values):
        import math
        if any(not math.isfinite(v) or abs(v) > 100000 for v in values):
            raise ValueError('Coordenadas inválidas')
        return values


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def name_valid(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('Informe um nome válido')
        return value


class ProjectUpdate(ProjectInput):
    revision: int = Field(ge=0)
    workspace: Workspace


def create_app(root=None):
    root = Path(root or os.environ.get('FORGE_STORAGE', Path(__file__).resolve().parents[1] / 'storage'))
    database = Database(root)
    app = FastAPI(title='FORGE Local API', version='0.1.0', docs_url=None, redoc_url=None)
    app.state.database = database
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and origin not in {'http://127.0.0.1:8765', 'http://localhost:8765', 'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:4173', 'http://localhost:4173'}:
            return JSONResponse({'detail': 'Origem não permitida'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Acesso externo bloqueado'}, status_code=403)
        if request.method in {'POST', 'PUT', 'PATCH'}:
            if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                return JSONResponse({'detail': 'JSON obrigatório'}, status_code=415)
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 32768:
                    return JSONResponse({'detail': 'Solicitação muito grande'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def serialize(row):
        if row is None:
            raise HTTPException(404, 'Projeto não encontrado')
        result = dict(row)
        result['workspace'] = json.loads(result['workspace'])
        result['asset_count'] = 0
        return result

    @app.get('/api/health')
    def health():
        with database.connect() as db:
            db.execute('SELECT 1')
        return {'status': 'ok', 'version': '0.1.0', 'local_only': True, 'database': 'ok'}

    @app.get('/api/providers')
    def providers():
        return [{'id': key, 'name': name, 'category': category, 'status': 'not_configured', 'enabled': False,
                 'reason': reason} for key, name, category, reason in [
                 ('flux', 'FLUX.1-schnell', 'concept', 'Provider previsto para a Fase 2. Nenhum modelo instalado pelo FORGE.'),
                 ('hunyuan', 'Hunyuan3D', 'model3d', 'Provider previsto para a Fase 3. Instalação e avaliação da licença pendentes.')]]

    @app.get('/api/system')
    @app.get('/api/diagnostics')
    def system():
        return diagnostics(database.root)

    @app.get('/api/projects')
    def projects():
        with database.connect() as db:
            return [serialize(row) for row in db.execute('SELECT * FROM projects ORDER BY updated_at DESC')]

    @app.post('/api/projects', status_code=201)
    def create_project(data: ProjectInput):
        project_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        database.prepare_project(project_id)
        with database.connect() as db:
            db.execute('INSERT INTO projects VALUES (?, ?, ?, ?, 0, ?)', (project_id, data.name, now, now, Workspace().model_dump_json()))
            return serialize(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())

    @app.get('/api/projects/{project_id}')
    def get_project(project_id: UUID):
        with database.connect() as db:
            return serialize(db.execute('SELECT * FROM projects WHERE id=?', (str(project_id),)).fetchone())

    @app.put('/api/projects/{project_id}')
    def update_project(project_id: UUID, data: ProjectUpdate):
        with database.connect() as db:
            serialize(db.execute('SELECT * FROM projects WHERE id=?', (str(project_id),)).fetchone())
            updated = db.execute('UPDATE projects SET name=?, workspace=?, revision=revision+1, updated_at=? WHERE id=? AND revision=?',
                (data.name, data.workspace.model_dump_json(), datetime.now(timezone.utc).isoformat(), str(project_id), data.revision))
            if updated.rowcount != 1:
                raise HTTPException(409, 'O projeto mudou em outra janela. Reabra o projeto antes de salvar.')
            return serialize(db.execute('SELECT * FROM projects WHERE id=?', (str(project_id),)).fetchone())

    dist = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
    # API misses must never fall through to the frontend.
    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def missing(path: str):
        raise HTTPException(404, 'Endpoint não encontrado')
    if dist.exists():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app
