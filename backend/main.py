import json
import os
import re
from contextlib import asynccontextmanager
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
from .services.storage import BlobStorage
from .services.assets import AssetService
from .services.tools import blender_path, unreal_installations
from .jobs import JobManager
from .api.studio import studio_router


class Workspace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    grid: bool = True
    environment: bool = True
    overlays: bool = True
    camera: list[float] = Field(default_factory=lambda: [12, 4, 12], min_length=3, max_length=3)
    target: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    selected_asset: UUID | None = None
    selected_version: UUID | None = None
    selected_object: str | None = Field(default=None, max_length=200)
    timeline_time: float = Field(default=0, ge=0, le=86400)
    timeline_visible: bool = False
    style: str = Field(default='', max_length=1000)
    gizmo: bool = True

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
    storage = BlobStorage(database.root)
    assets = AssetService(database, storage)
    jobs = JobManager(database)

    @asynccontextmanager
    async def lifespan(app):
        jobs.start()
        yield
        jobs.close()

    app = FastAPI(title='FORGE Local API', version='0.2.0', docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.database = database
    app.state.assets = assets
    app.state.jobs = jobs
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and origin not in {'http://127.0.0.1:8765', 'http://localhost:8765', 'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:4173', 'http://localhost:4173'}:
            return JSONResponse({'detail': 'Origem não permitida'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Acesso externo bloqueado'}, status_code=403)
        if request.method in {'POST', 'PUT', 'PATCH'}:
            is_binary = request.method == 'POST' and bool(re.fullmatch(r'/api/(projects/[a-f0-9-]+/assets/import|assets/[a-f0-9-]+/versions)', request.url.path))
            content_type = request.headers.get('content-type', '').split(';')[0]
            empty_body = request.headers.get('content-length') == '0' or request.headers.get('content-length') is None and request.method in {'POST', 'PUT', 'PATCH'} and request.url.path.endswith(('/variants', '/restore'))
            if not is_binary and not empty_body and content_type != 'application/json':
                return JSONResponse({'detail': 'JSON obrigatório'}, status_code=415)
            if is_binary and content_type != 'application/octet-stream':
                return JSONResponse({'detail': 'Upload deve usar application/octet-stream'}, status_code=415)
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > (128*1024*1024 if is_binary else 32768):
                    return JSONResponse({'detail': 'Solicitação muito grande'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(ValueError)
    async def invalid_data(request, error):
        return JSONResponse({'detail': str(error)[:1000]}, status_code=422)

    def serialize(row):
        if row is None:
            raise HTTPException(404, 'Projeto não encontrado')
        result = dict(row)
        result['workspace'] = json.loads(result['workspace'])
        with database.connect() as db:
            result['asset_count'] = db.execute('SELECT COUNT(*) FROM assets WHERE project_id=? AND archived=0', (row['id'],)).fetchone()[0]
        return result

    @app.get('/api/health')
    def health():
        with database.connect() as db:
            db.execute('SELECT 1')
        return {'status': 'ok', 'version': '0.2.0', 'local_only': True, 'database': 'ok', 'worker': bool(jobs.thread and jobs.thread.is_alive()), 'storage': str(database.root)}

    @app.get('/api/system')
    @app.get('/api/diagnostics')
    def system():
        return diagnostics(database.root) | {'blender': blender_path(), 'unreal_installations': unreal_installations(), 'worker': bool(jobs.thread and jobs.thread.is_alive())}

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
        if data.workspace.selected_asset:
            selected = assets.get(data.workspace.selected_asset, data.workspace.selected_version)
            if selected['project_id'] != str(project_id):
                raise HTTPException(422, 'Seleção pertence a outro projeto.')
        with database.connect() as db:
            serialize(db.execute('SELECT * FROM projects WHERE id=?', (str(project_id),)).fetchone())
            updated = db.execute('UPDATE projects SET name=?, workspace=?, revision=revision+1, updated_at=? WHERE id=? AND revision=?',
                (data.name, data.workspace.model_dump_json(), datetime.now(timezone.utc).isoformat(), str(project_id), data.revision))
            if updated.rowcount != 1:
                raise HTTPException(409, 'O projeto mudou em outra janela. Reabra o projeto antes de salvar.')
            return serialize(db.execute('SELECT * FROM projects WHERE id=?', (str(project_id),)).fetchone())

    app.include_router(studio_router(database, assets, jobs))
    dist = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
    # API misses must never fall through to the frontend.
    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def missing(path: str):
        raise HTTPException(404, 'Endpoint não encontrado')
    if dist.exists():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app
