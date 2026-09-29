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
            # Additive migrations preserve existing Phase 1 projects.
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    name TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL,
                    parent_id TEXT, current_version TEXT, tags TEXT NOT NULL DEFAULT '[]',
                    favorite INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
                    number INTEGER NOT NULL, parent_id TEXT, blob TEXT NOT NULL,
                    metadata TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(asset_id, number));
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    type TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                    priority INTEGER NOT NULL, payload TEXT NOT NULL, result TEXT,
                    error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS assets_project ON assets(project_id, archived);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, priority, created_at);
                CREATE TABLE IF NOT EXISTS exports (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_id TEXT,
                    version_id TEXT, format TEXT NOT NULL, blob TEXT NOT NULL,
                    metadata TEXT NOT NULL, created_at TEXT NOT NULL);
                PRAGMA user_version=2;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'forge.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def prepare_project(self, project_id):
        root = self.root / 'projects' / project_id
        for name in ('concepts', 'assets', 'textures', 'animations', 'vfx', 'particles', 'audio', 'exports', 'references'):
            (root / name).mkdir(parents=True, exist_ok=True)
