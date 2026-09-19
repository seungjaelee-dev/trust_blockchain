"""Collect notices from a locally built image; all containers run offline.

Run with host Python in Linux/WSL. This collects shipped notices and inventories,
not corresponding source archives or a legal opinion about redistribution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


INSPECT = r'''
import hashlib, importlib.metadata as md, json, platform, subprocess
from pathlib import Path
packages, texts = [], []
for dist in sorted(md.distributions(), key=lambda d: d.metadata['Name'].lower()):
    meta = dist.metadata
    notices = []
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ('license', 'copying', 'notice', 'authors')):
            path = dist.locate_file(file)
            if not path.is_file() or path.suffix in ('.py', '.pyc', '.so'):
                continue
            raw = path.read_bytes()
            notices.append({'path': str(file), 'sha256': hashlib.sha256(raw).hexdigest()})
            texts.append('\n===== ' + meta['Name'] + ' ' + dist.version + ' / ' + str(file) + ' =====\n' + raw.decode('utf-8', errors='replace'))
    packages.append({'name': meta['Name'], 'version': dist.version,
        'license_expression': meta.get('License-Expression'),
        'license_metadata': meta.get('License'),
        'license_classifiers': [x for x in meta.get_all('Classifier', []) if x.startswith('License ::')],
        'homepage': meta.get('Home-page'), 'project_urls': meta.get_all('Project-URL', []),
        'notices': notices})
base = []
for path in sorted(set(Path('/usr/share/doc').glob('*/copyright')) | set(Path('/usr/share/common-licenses').glob('*')) | set(Path('/usr/local/lib').glob('python*/LICENSE.txt'))):
    if path.is_file():
        base.append('\n===== ' + str(path) + ' =====\n' + path.read_text(errors='replace'))
os_packages = subprocess.check_output(['dpkg-query', '-W', '-f', '${Package}\t${Version}\t${source:Package}\t${source:Version}\n'], text=True)
print(json.dumps({'python': platform.python_version(), 'packages': packages,
    'python_notices': '\n'.join(texts), 'base_notices': '\n'.join(base),
    'os_packages': os_packages}, ensure_ascii=False))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dest = root / 'third_party'
    dest.mkdir(exist_ok=True)
    image_id = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    data = json.loads(subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python', image_id, '-c', INSPECT], text=True))
    solc = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/usr/local/bin/solc', image_id, '--license'])
    outputs = {'PYTHON-LICENSES.txt': data.pop('python_notices').encode(),
               'BASE-IMAGE-COPYRIGHT.txt': data.pop('base_notices').encode(),
               'OS-PACKAGES.tsv': data.pop('os_packages').encode(), 'SOLC-LICENSE.txt': solc}
    for name, raw in outputs.items():
        (dest / name).write_bytes(raw)
    installed = {p['name'].lower().replace('_', '-'): p['version'] for p in data['packages']}
    lock = root / 'docker/requirements.lock'
    for line in lock.read_text().splitlines():
        if line and not line.startswith('#'):
            name, version = line.split('==')
            assert installed[name.lower().replace('_', '-')] == version, line
    data.update(image=args.image, image_id=image_id, requirements_sha256=hashlib.sha256(lock.read_bytes()).hexdigest(),
                files_sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in outputs.items()},
                scope='Notices shipped in the selected image; not corresponding source archives.')
    (dest / 'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'packages': len(installed), 'without_notice_file': [p['name'] for p in data['packages'] if not p['notices']],
                      'bytes': sum(len(raw) for raw in outputs.values()), 'image_id': image_id}, indent=2))


if __name__ == '__main__':
    main()
