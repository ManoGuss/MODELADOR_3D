import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from ..validators.files import inspect_audio, inspect_glb, inspect_image


def now():
    return datetime.now(timezone.utc).isoformat()


class AssetService:
    def __init__(self, database, storage):
        self.db, self.storage = database, storage

    def project(self, project_id):
        with self.db.connect() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (str(project_id),)).fetchone()
        if not row:
            raise HTTPException(404, 'Projeto não encontrado.')
        return dict(row)

    def list(self, project_id, query='', kind='', sort='recent', archived=False):
        self.project(project_id)
        order = {'recent': 'updated_at DESC', 'name': 'name COLLATE NOCASE', 'type': 'kind, name'}.get(sort, 'updated_at DESC')
        with self.db.connect() as db:
            rows = db.execute(f'SELECT id FROM assets WHERE project_id=? AND archived=? ORDER BY {order}', (str(project_id), int(archived))).fetchall()
        results = [self.get(row['id']) for row in rows]
        return [a for a in results if (not kind or a['kind'] == kind) and (not query or query.casefold() in (a['name']+' '+' '.join(a['tags'])).casefold())]

    def get(self, asset_id, version_id=None):
        with self.db.connect() as db:
            row = db.execute('SELECT * FROM assets WHERE id=?', (str(asset_id),)).fetchone()
            if not row:
                raise HTTPException(404, 'Asset não encontrado.')
            asset = dict(row)
            version = db.execute('SELECT * FROM versions WHERE asset_id=? AND id=?', (str(asset_id), str(version_id or asset['current_version']))).fetchone()
        if not version:
            raise HTTPException(404, 'Versão não encontrada.')
        asset['tags'] = json.loads(asset['tags'])
        asset['favorite'], asset['archived'] = bool(asset['favorite']), bool(asset['archived'])
        asset['version'] = dict(version)
        asset['version']['metadata'] = json.loads(version['metadata'])
        asset['url'] = f"/api/assets/{asset['id']}/file?version_id={version['id']}"
        return asset

    def versions(self, asset_id):
        self.get(asset_id)
        with self.db.connect() as db:
            rows = db.execute('SELECT * FROM versions WHERE asset_id=? ORDER BY number DESC', (str(asset_id),)).fetchall()
        return [dict(row) | {'metadata': json.loads(row['metadata'])} for row in rows]

    def import_file(self, project_id, name, content, category='model', provenance=None):
        self.project(project_id)
        if not name.strip() or len(name) > 100 or any(ord(c) < 32 for c in name):
            raise ValueError('Nome de asset inválido.')
        if category == 'model':
            metadata = inspect_glb(content)
            kind, extension = metadata['kind'], 'glb'
        elif category in {'reference', 'sketch', 'concept'}:
            metadata = inspect_image(content)
            kind, extension = category, metadata['extension']
        elif category == 'audio':
            metadata = inspect_audio(content)
            kind, extension = category, 'wav'
        elif category == 'particles':
            from ..domain.contracts import Effect
            effect = Effect.model_validate_json(content)
            if effect.attachment and self.get(effect.attachment)['project_id'] != str(project_id):
                raise ValueError('O vínculo deve pertencer ao mesmo projeto.')
            metadata = effect.model_dump(mode='json')
            kind, extension = category, 'json'
        else:
            raise ValueError('Tipo não suportado.')
        source = (provenance or {}).get('source', 'Imported')
        metadata['provenance'] = provenance or {'source': source, 'license': 'Fornecida pelo usuário; direitos não verificados'}
        blob = self.storage.put(content, extension)
        asset_id, version_id, timestamp = str(uuid4()), str(uuid4()), now()
        with self.db.connect() as db:
            db.execute('INSERT INTO assets(id,project_id,name,kind,source,current_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', (asset_id, str(project_id), name.strip(), kind, source, version_id, timestamp, timestamp))
            db.execute('INSERT INTO versions VALUES (?,?,1,NULL,?,?,?)', (version_id, asset_id, blob, json.dumps(metadata), timestamp))
        return self.get(asset_id)

    def add_version(self, asset_id, content, parent_id, metadata_extra=None):
        asset = self.get(asset_id)
        if asset['kind'] not in {'static_mesh', 'skeletal_mesh'}:
            raise ValueError('Edição GLB exige um modelo selecionado.')
        metadata = inspect_glb(content)
        metadata['provenance'] = asset['version']['metadata'].get('provenance', {}) | {'source': 'Modified'}
        metadata.update(metadata_extra or {})
        blob = self.storage.put(content, 'glb')
        return self._append(asset_id, parent_id, blob, metadata, metadata['kind'])

    def _append(self, asset_id, parent_id, blob, metadata, kind=None):
        identifier, timestamp = str(uuid4()), now()
        with self.db.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT current_version, kind FROM assets WHERE id=?', (str(asset_id),)).fetchone()
            if not row or row['current_version'] != str(parent_id):
                raise HTTPException(409, 'Existe uma versão mais recente. Reabra o asset antes de salvar.')
            number = db.execute('SELECT MAX(number)+1 FROM versions WHERE asset_id=?', (str(asset_id),)).fetchone()[0]
            db.execute('INSERT INTO versions VALUES (?,?,?,?,?,?,?)', (identifier, str(asset_id), number, str(parent_id), blob, json.dumps(metadata), timestamp))
            db.execute('UPDATE assets SET current_version=?,kind=?,updated_at=? WHERE id=?', (identifier, kind or row['kind'], timestamp, str(asset_id)))
        return self.get(asset_id)

    def restore(self, asset_id, version_id):
        current = self.get(asset_id)
        old = self.get(asset_id, version_id)
        self.storage.read(old['version']['blob'])
        metadata = old['version']['metadata'] | {'restored_from': str(version_id)}
        return self._append(asset_id, current['current_version'], old['version']['blob'], metadata, metadata.get('kind', current['kind']))

    def duplicate(self, asset_id):
        original = self.get(asset_id)
        identifier, version_id, timestamp = str(uuid4()), str(uuid4()), now()
        with self.db.connect() as db:
            db.execute('INSERT INTO assets(id,project_id,name,kind,source,parent_id,current_version,tags,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (identifier, original['project_id'], original['name'][:85]+' · Variante', original['kind'], original['source'], str(asset_id), version_id, json.dumps(original['tags']), timestamp, timestamp))
            db.execute('INSERT INTO versions VALUES (?,?,1,?,?,?,?)', (version_id, identifier, original['current_version'], original['version']['blob'], json.dumps(original['version']['metadata']), timestamp))
        return self.get(identifier)

    def update(self, asset_id, update):
        self.get(asset_id)
        with self.db.connect() as db:
            db.execute('UPDATE assets SET name=?,tags=?,favorite=?,archived=?,updated_at=? WHERE id=?',
                       (update.name, json.dumps(update.tags), int(update.favorite), int(update.archived), now(), str(asset_id)))
        return self.get(asset_id)
