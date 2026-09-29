import json
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from ..services.tools import blender_path


def export_fbx(content, root, cancelled, stage):
    executable = blender_path()
    if not executable:
        raise ValueError('Blender não detectado. Instale-o ou configure FORGE_BLENDER para exportar FBX.')
    with tempfile.TemporaryDirectory(prefix='fbx-', dir=Path(root)/'tmp') as directory:
        directory = Path(directory)
        source, output, report = directory/'source.glb', directory/'asset.fbx', directory/'report.json'
        source.write_bytes(content)
        request = directory/'request.json'
        request.write_text(json.dumps({'input': str(source), 'output': str(output), 'report': str(report)}), encoding='utf-8')
        script = Path(__file__).resolve().parents[1]/'workers/blender_export.py'
        stage('processing', 'Convertendo e validando FBX no Blender')
        with (directory/'blender.log').open('wb') as log:
            process = subprocess.Popen([executable, '--background', '--factory-startup', '--disable-autoexec', '--python', str(script), '--', str(request)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                deadline = time.monotonic()+300
                while process.poll() is None:
                    if cancelled():
                        raise InterruptedError('Exportação cancelada.')
                    if time.monotonic() > deadline:
                        raise TimeoutError('Blender excedeu cinco minutos na exportação.')
                    time.sleep(.25)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
        if process.returncode or not output.is_file() or not report.is_file():
            details = (directory/'blender.log').read_text(errors='replace')[-3000:]
            raise ValueError('Blender não concluiu exportação e round trip. '+details)
        result = output.read_bytes()
        if not result.startswith(b'Kaydara FBX Binary  \x00\x1a\x00') or len(result) < 1024:
            raise ValueError('Blender retornou um FBX inválido.')
        metadata = json.loads(report.read_text())
        metadata['fbx_binary_version'] = struct.unpack_from('<I', result, 23)[0]
        metadata['fbx_profile_version'] = '1.0.0'
        metadata['unreal_verified_versions'] = []
        return result, metadata
