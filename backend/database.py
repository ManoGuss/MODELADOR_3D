import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                workspace TEXT NOT NULL DEFAULT '{}')''')
            db.execute('PRAGMA user_version=1')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'forge.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def prepare_project(self, project_id):
        root = self.root / 'projects' / project_id
        for name in ('concepts', 'assets', 'textures', 'animations', 'vfx', 'particles', 'audio', 'exports', 'references'):
            (root / name).mkdir(parents=True, exist_ok=True)
