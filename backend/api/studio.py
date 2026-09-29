import asyncio
import io
import json
import secrets
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image
from ..domain.contracts import Settings, PROFILES, Generate, AssetUpdate, ExportRequest, RestoreRequest, Effect
from ..services.assets import now
from ..services.tools import blender_path, unreal_installations
from ..providers.comfy import ComfyProvider
from ..exporters.blender import export_fbx
from ..exporters.packages import asset_package, build_package, technical_name


def studio_router(database, assets, jobs):
    router = APIRouter(prefix='/api')

    def settings():
        with database.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key='studio'").fetchone()
        return Settings.model_validate_json(row['value']) if row else Settings()

    def generation(job, cancelled, stage):
        payload = job['payload']
        config = Settings.model_validate(payload['settings'])
        data, provenance = ComfyProvider(config).generate(payload | {'request_id': job['id']}, assets, cancelled, stage)
        if cancelled():
            raise InterruptedError('Geração cancelada; resultado descartado.')
        stage('finalizing', 'Salvando concept no projeto')
        result = assets.import_file(job['project_id'], payload['prompt'][:80], data, 'concept', provenance)
        return {'asset_id': result['id']}

    def export(job, cancelled, stage):
        payload = job['payload']
        stage('post_processing', 'Validando arquivos e dependências')
        if payload['format'] == 'project':
            project = assets.project(job['project_id'])
            files = {'project.json': json.dumps(project, ensure_ascii=False, indent=2).encode()}
            all_assets = assets.list(job['project_id'])+assets.list(job['project_id'], archived=True)
            files['assets.json'] = json.dumps(all_assets, ensure_ascii=False, indent=2).encode()
            for asset in all_assets:
                versions = assets.versions(asset['id'])
                files[f"assets/{asset['id']}/versions.json"] = json.dumps(versions, ensure_ascii=False).encode()
                for version in versions:
                    if cancelled():
                        raise InterruptedError('Backup cancelado.')
                    files[f"blobs/{version['blob']}"] = assets.storage.read(version['blob'])
            files['LICENSES.txt'] = b'Licenses and content provenance are preserved in each version metadata. FORGE claims no ownership.\n'
            data, metadata = build_package(files, {'schemaVersion': 1, 'projectId': job['project_id'], 'type': 'project', 'forgeVersion': '0.2.0'})
            extension, asset_id, version_id = 'zip', None, None
        else:
            asset = assets.get(payload['asset_id'], payload['version_id'])
            asset_id, version_id = asset['id'], asset['version']['id']
            data = assets.storage.read(asset['version']['blob'])
            extension = payload['format']
            metadata = {'sourceForgeAssetId': asset_id, 'sourceForgeVersion': asset['version']['number']}
            if extension == 'fbx':
                data, report = export_fbx(data, database.root, cancelled, stage)
                metadata.update(report)
            elif extension in {'zip', 'unreal'}:
                data, report = asset_package(asset, data)
                metadata.update(report)
                extension = 'zip'
            elif extension != 'glb' or asset['kind'] not in {'static_mesh', 'skeletal_mesh'}:
                raise ValueError('Este asset não pode ser exportado como GLB.')
        if cancelled():
            raise InterruptedError('Exportação cancelada.')
        stage('finalizing', 'Verificando integridade e salvando exportação')
        blob = assets.storage.put(data, extension)
        identifier = str(uuid4())
        with database.connect() as db:
            db.execute('INSERT INTO exports VALUES (?,?,?,?,?,?,?,?)', (identifier, job['project_id'], asset_id, version_id, extension, blob, json.dumps(metadata), now()))
        return {'export_id': identifier, 'url': f'/api/exports/{identifier}/file', 'format': extension,
                'sha256': blob.split('.')[0], 'bytes': len(data), 'report': metadata}

    jobs.handlers.update(concept=generation, export=export)

    @router.get('/settings')
    def get_settings():
        return settings().model_dump() | {'profiles': PROFILES, 'local_only': True, 'blender': blender_path(), 'unreal_installations': unreal_installations()}

    @router.put('/settings')
    def set_settings(config: Settings):
        with database.connect() as db:
            db.execute("INSERT INTO settings VALUES ('studio',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (config.model_dump_json(),))
        return get_settings()

    @router.get('/providers')
    def providers():
        return [ComfyProvider(settings()).status(), {'id': 'hunyuan', 'name': 'Hunyuan3D', 'category': 'model3d', 'status': 'not_configured', 'enabled': False,
                 'capabilities': {'imageTo3D': False}, 'reason': 'Runtime, pesos e licença ainda não configurados. Nenhuma geração 3D será simulada.'}]

    @router.post('/concepts/generate', status_code=202)
    def generate(payload: Generate):
        project = assets.project(payload.project_id)
        config = settings()
        available = ComfyProvider(config).status()
        if not available['enabled']:
            raise HTTPException(409, available['reason'])
        for identifier in (payload.reference_id, payload.sketch_id):
            if identifier and assets.get(identifier)['project_id'] != str(payload.project_id):
                raise HTTPException(422, 'Referência pertence a outro projeto.')
        data = payload.model_dump(mode='json') | {'seed': payload.seed if payload.seed is not None else secrets.randbelow(2**53), 'settings': config.model_dump(), 'project_context': json.loads(project['workspace']).get('style', '')}
        if data['project_context']:
            data['prompt'] += '\nEstilo do projeto: '+data['project_context']
        return jobs.submit(payload.project_id, 'concept', data, payload.priority)

    @router.post('/models/generate')
    def generate_model(payload: Generate):
        assets.project(payload.project_id)
        raise HTTPException(409, 'Nenhum provider 3D local compatível está configurado. Você pode importar um GLB real.')

    @router.get('/projects/{project_id}/assets')
    def list_assets(project_id: UUID, q: str = Query('', max_length=100), kind: str = '', sort: str = 'recent', archived: bool = False):
        return assets.list(project_id, q, kind, sort, archived)

    @router.post('/projects/{project_id}/assets/import', status_code=201)
    async def import_asset(project_id: UUID, request: Request, name: str = Query(min_length=1, max_length=100), category: str = 'model'):
        data = await request.body()
        if not data:
            raise HTTPException(422, 'Arquivo vazio.')
        return await asyncio.to_thread(assets.import_file, project_id, name, data, category)

    @router.get('/assets/{asset_id}')
    def get_asset(asset_id: UUID, version_id: UUID | None = None):
        return assets.get(asset_id, version_id)

    @router.get('/assets/{asset_id}/file')
    def asset_file(asset_id: UUID, version_id: UUID | None = None, preview: bool = False):
        asset = assets.get(asset_id, version_id)
        blob = asset['version']['blob']
        assets.storage.read(blob)
        if preview and asset['kind'] in {'concept', 'reference', 'sketch'}:
            with Image.open(assets.storage.path(blob)) as image:
                image.thumbnail((512, 512))
                buffer = io.BytesIO()
                image.convert('RGB').save(buffer, 'JPEG', quality=85)
            from fastapi.responses import Response
            return Response(buffer.getvalue(), media_type='image/jpeg', headers={'Cache-Control': 'private,max-age=86400'})
        return FileResponse(assets.storage.path(blob), media_type={'glb': 'model/gltf-binary', 'wav': 'audio/wav', 'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp', 'json': 'application/json'}.get(blob.split('.')[-1], 'application/octet-stream'), headers={'Cache-Control': 'private,max-age=86400'})

    @router.put('/assets/{asset_id}')
    def update(asset_id: UUID, payload: AssetUpdate):
        return assets.update(asset_id, payload)

    @router.get('/assets/{asset_id}/versions')
    def versions(asset_id: UUID):
        return assets.versions(asset_id)

    @router.post('/assets/{asset_id}/versions', status_code=201)
    async def version(asset_id: UUID, parent_id: UUID, request: Request):
        return await asyncio.to_thread(assets.add_version, asset_id, await request.body(), parent_id)

    @router.post('/assets/{asset_id}/restore')
    def restore(asset_id: UUID, payload: RestoreRequest):
        return assets.restore(asset_id, payload.version_id)

    @router.post('/assets/{asset_id}/variants', status_code=201)
    def duplicate(asset_id: UUID):
        return assets.duplicate(asset_id)

    @router.get('/assets/{asset_id}/variants')
    def variants(asset_id: UUID):
        asset = assets.get(asset_id)
        return [item for item in assets.list(asset['project_id']) if item['parent_id'] == str(asset_id)]

    @router.post('/projects/{project_id}/particles', status_code=201)
    def particles(project_id: UUID, effect: Effect):
        return assets.import_file(project_id, 'Partículas', effect.model_dump_json().encode(), 'particles', {'source': 'Procedural', 'provider': 'forge-particles', 'license': 'Definição criada pelo usuário.'})

    @router.post('/assets/{asset_id}/export', status_code=202)
    def export_asset(asset_id: UUID, payload: ExportRequest):
        asset = assets.get(asset_id, payload.version_id)
        if payload.format == 'unreal':
            raise HTTPException(409, 'Use Enviar para Unreal com uma instância Bridge validada, ou exporte FBX/ZIP.')
        if payload.format in {'fbx', 'glb'} and asset['kind'] not in {'static_mesh', 'skeletal_mesh'}:
            raise HTTPException(422, 'Este formato exige uma mesh real.')
        if payload.format == 'fbx' and not blender_path():
            raise HTTPException(409, 'Blender não configurado para exportação FBX.')
        return jobs.submit(asset['project_id'], 'export', {'asset_id': str(asset_id), 'version_id': asset['version']['id'], 'format': payload.format})

    @router.post('/projects/{project_id}/backup', status_code=202)
    def backup(project_id: UUID):
        assets.project(project_id)
        return jobs.submit(project_id, 'export', {'format': 'project'}, 'background')

    @router.get('/exports/{export_id}/file')
    def download(export_id: UUID):
        with database.connect() as db:
            row = db.execute('SELECT * FROM exports WHERE id=?', (str(export_id),)).fetchone()
        if not row:
            raise HTTPException(404, 'Exportação não encontrada.')
        assets.storage.read(row['blob'])
        name = 'FORGE_Projeto'
        if row['asset_id']:
            asset = assets.get(row['asset_id'], row['version_id'])
            name = technical_name(asset['name'], asset['kind']) if asset['kind'] in {'static_mesh', 'skeletal_mesh', 'particles', 'audio'} else 'FORGE_Asset'
        return FileResponse(assets.storage.path(row['blob']), filename=f"{name}.{row['format']}")

    @router.get('/projects/{project_id}/jobs')
    def list_jobs(project_id: UUID):
        assets.project(project_id)
        return jobs.list(project_id)

    @router.get('/jobs/{job_id}')
    def get_job(job_id: UUID):
        return jobs.get(job_id)

    @router.post('/jobs/{job_id}/cancel')
    def cancel_job(job_id: UUID):
        return jobs.cancel(job_id)

    @router.post('/jobs/{job_id}/retry', status_code=202)
    def retry_job(job_id: UUID):
        return jobs.retry(job_id)

    @router.get('/projects/{project_id}/events')
    async def events(project_id: UUID, request: Request):
        assets.project(project_id)
        async def stream():
            previous, count = '', 0
            while not await request.is_disconnected():
                data = json.dumps(await asyncio.to_thread(jobs.list, project_id), ensure_ascii=False)
                if data != previous:
                    yield f'event: jobs\ndata: {data}\n\n'
                    previous = data
                elif count % 15 == 0:
                    yield ': keepalive\n\n'
                count += 1
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    return router
