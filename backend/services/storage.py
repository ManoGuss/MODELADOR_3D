import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4


class BlobStorage:
    """Immutable, content-addressed files. User paths are never used on disk."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        (self.root / 'blobs').mkdir(exist_ok=True)
        (self.root / 'tmp').mkdir(exist_ok=True)

    def put(self, content: bytes, extension: str):
        if extension not in {'glb', 'png', 'jpg', 'webp', 'wav', 'json', 'zip', 'fbx'}:
            raise ValueError('Formato não permitido')
        digest = hashlib.sha256(content).hexdigest()
        name = f'{digest}.{extension}'
        target = self.path(name)
        if not target.exists():
            temporary = self.root / 'tmp' / str(uuid4())
            try:
                with temporary.open('xb') as file:
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return name

    def path(self, name):
        if not re.fullmatch(r'[a-f0-9]{64}\.(glb|png|jpg|webp|wav|json|zip|fbx)', name):
            raise ValueError('Referência de arquivo inválida')
        return self.root / 'blobs' / name

    def read(self, name):
        data = self.path(name).read_bytes()
        if hashlib.sha256(data).hexdigest() != name.split('.')[0]:
            raise ValueError('A integridade do arquivo falhou (SHA-256).')
        return data
