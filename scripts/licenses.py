"""Offline inventory of the installed, locked environment; does not approve AI weights."""
import importlib.metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows = []


def record(name, version, license, url, ecosystem):
    permissive = license in {'MIT', 'BSD-2-Clause', 'BSD-3-Clause', 'Apache-2.0', 'PSF-2.0', 'Apache-2.0 OR BSD-2-Clause', '0BSD', 'ISC'}
    rows.append(dict(name=name, version=version, license=license or 'Revisão necessária', officialUrl=url,
                     ecosystem=ecosystem, isLocal=True, isFree=True, requiresApiKey=False,
                     requiresCredits=False, requiresSubscription=False,
                     commercialUse='Permitido sob condições da licença' if permissive else 'Revisar licença',
                     redistributionAllowed='Preservar licença e avisos' if permissive else 'Revisar licença',
                     weightsRedistribution='Não aplicável', attributionRequired=license != '0BSD',
                     territorialRestrictions='Nenhuma identificada' if permissive else 'Não avaliado',
                     usageRestrictions='Preservar avisos; não conceder endosso dos autores',
                     licenseCompatible=permissive))


for dist in importlib.metadata.distributions():
    metadata = dist.metadata
    license = metadata.get('License-Expression') or metadata.get('License', '').split('\n')[0]
    if not license:
        license = next((c.rsplit(' :: ', 1)[-1].replace(' License', '') for c in metadata.get_all('Classifier', []) if c.startswith('License ::')), '')
    if metadata['Name'] == 'colorama' and dist.version == '0.4.6':
        license = 'BSD-3-Clause'  # Confirmed in installed licenses/LICENSE.txt.
    url = metadata.get('Home-page') or next(iter(metadata.get_all('Project-URL', [])), '').split(', ')[-1]
    record(metadata['Name'], dist.version, license, url, 'python')

for package in (ROOT / 'frontend' / 'node_modules' / '.pnpm').glob('*/node_modules/*/package.json'):
    data = json.loads(package.read_text(encoding='utf-8'))
    record(data['name'], data['version'], data.get('license', ''), data.get('homepage', ''), 'npm')
for package in (ROOT / 'frontend' / 'node_modules' / '.pnpm').glob('*/node_modules/@*/*/package.json'):
    data = json.loads(package.read_text(encoding='utf-8'))
    record(data['name'], data['version'], data.get('license', ''), data.get('homepage', ''), 'npm')

unique = {(r['ecosystem'], r['name'], r['version']): r for r in rows}
(ROOT / 'docs' / 'license-registry.json').write_text(json.dumps(sorted(unique.values(), key=lambda r: (r['ecosystem'], r['name'])), ensure_ascii=False, indent=2), encoding='utf-8')
print(f'{len(unique)} pacotes registrados. Revisões pendentes:', [r['name'] for r in unique.values() if not r['licenseCompatible']])
