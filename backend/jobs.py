import json
import threading
import time
from uuid import uuid4
from fastapi import HTTPException
from .services.assets import now

TERMINAL = {'completed', 'failed', 'cancelled'}


class JobManager:
    """Persistent sequential worker: GPU/export workloads never overlap in this process."""
    def __init__(self, database):
        self.db = database
        self.handlers = {}
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = None

    def start(self):
        with self.db.connect() as db:
            db.execute("UPDATE jobs SET status='failed',stage='Interrompido pelo reinício',error='Backend reiniciado durante a operação.',updated_at=? WHERE status NOT IN ('queued','completed','failed','cancelled')", (now(),))
        self.thread = threading.Thread(target=self.run, daemon=True, name='forge-worker')
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=12)

    def get(self, job_id):
        with self.db.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (str(job_id),)).fetchone()
        if not row:
            raise HTTPException(404, 'Job não encontrado.')
        item = dict(row)
        item['payload'] = json.loads(item['payload'])
        item['result'] = json.loads(item['result']) if item['result'] else None
        return item

    def list(self, project_id):
        with self.db.connect() as db:
            rows = db.execute('SELECT id FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 100', (str(project_id),)).fetchall()
        return [self.get(row['id']) for row in rows]

    def submit(self, project_id, kind, payload, priority='normal'):
        if kind not in self.handlers:
            raise HTTPException(409, 'O motor configurado atualmente não suporta essa operação.')
        identifier, timestamp = str(uuid4()), now()
        with self.db.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM jobs WHERE status NOT IN ('completed','failed','cancelled')").fetchone()[0]
            if count >= 20:
                raise HTTPException(429, 'A fila está cheia. Aguarde ou cancele uma tarefa.')
            db.execute('INSERT INTO jobs(id,project_id,type,status,stage,priority,payload,created_at,updated_at) VALUES (?,?,?,\'queued\',\'Na fila\',?,?,?,?)',
                       (identifier, str(project_id), kind, {'interactive': 0, 'normal': 1, 'background': 2}[priority], json.dumps(payload), timestamp, timestamp))
        self.wake.set()
        return self.get(identifier)

    def cancel(self, job_id):
        job = self.get(job_id)
        if job['status'] not in TERMINAL:
            with self.db.connect() as db:
                db.execute("UPDATE jobs SET cancel_requested=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated_at=? WHERE id=?", (now(), str(job_id)))
        return self.get(job_id)

    def retry(self, job_id):
        job = self.get(job_id)
        if job['status'] not in {'failed', 'cancelled'}:
            raise HTTPException(409, 'Somente tarefas falhadas/canceladas podem ser repetidas.')
        return self.submit(job['project_id'], job['type'], job['payload'] | {'retry_of': str(job_id)})

    def stage(self, job_id, status, stage):
        with self.db.connect() as db:
            db.execute('UPDATE jobs SET status=?,stage=?,updated_at=? WHERE id=?', (status, stage, now(), job_id))

    def run(self):
        while not self.stop.is_set():
            with self.db.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY priority,created_at LIMIT 1").fetchone()
                if row:
                    db.execute("UPDATE jobs SET status='preparing',stage='Preparando',updated_at=? WHERE id=?", (now(), row['id']))
            if not row:
                self.wake.wait(1)
                self.wake.clear()
                continue
            identifier = row['id']
            job = self.get(identifier)
            start = time.monotonic()
            cancelled = lambda: self.stop.is_set() or bool(self.get(identifier)['cancel_requested'])
            try:
                if cancelled():
                    raise InterruptedError('Tarefa cancelada.')
                result = self.handlers[job['type']](job, cancelled, lambda state, label: self.stage(identifier, state, label))
                # A handler commits outputs only after checking cancellation.
                result['duration_seconds'] = round(time.monotonic()-start, 3)
                with self.db.connect() as db:
                    db.execute("UPDATE jobs SET status='completed',stage='Concluído',result=?,updated_at=? WHERE id=?", (json.dumps(result), now(), identifier))
            except Exception as error:
                state = 'cancelled' if isinstance(error, InterruptedError) else 'failed'
                message = str(error)
                if 'out of memory' in message.lower():
                    message = 'A GPU não possui memória suficiente. Selecione Economia de VRAM.'
                with self.db.connect() as db:
                    db.execute('UPDATE jobs SET status=?,stage=?,error=?,updated_at=? WHERE id=?', (state, 'Cancelado' if state == 'cancelled' else 'Falha na operação', message[:2000], now(), identifier))
