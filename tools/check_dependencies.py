#!/usr/bin/env python3
"""Validate operational dependency metadata against the preserved source catalog."""
import configparser
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DISPOSITIONS = {
    'pinned-submodule', 'installed-package-or-explicit-source',
    'installed-package-for-manual-folly-build', 'catalog-only',
}


def validate(root=ROOT):
    record = json.loads((root / 'docs/meta/dependency-declarations.json').read_text())
    rows = record['entries']
    errors = []
    paths = [row['path'] for row in rows]
    if len(rows) != record['declaration_count'] or len(set(paths)) != len(paths):
        errors.append('Historical dependency catalog is incomplete or duplicated')
    config = configparser.ConfigParser()
    config.read(root / '.gitmodules')
    declarations = {config[s]['path']: config[s]['url'] for s in config.sections()}
    links = {}
    for entry in subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root).decode().split('\0'):
        if entry.startswith('160000 '):
            metadata, path = entry.split('\t', 1)
            links[path] = metadata.split()[1]
    if links != record['preserved_gitlinks']:
        errors.append('Tracked gitlinks differ from preserved dependency pins')
    if len(declarations) != len(config.sections()) or set(declarations) != set(links):
        errors.append('.gitmodules must describe exactly the tracked gitlinks')
    for row in rows:
        path = row['path']
        if row.get('current_disposition') not in DISPOSITIONS:
            errors.append(f'{path}: missing/invalid current disposition')
        if not row.get('original_url') or not row.get('declaration', {}).get('blob_sha'):
            errors.append(f'{path}: lost historical URL or declaration evidence')
        if row['gitlink_sha']:
            if row.get('current_disposition') != 'pinned-submodule':
                errors.append(f'{path}: a pinned gitlink cannot be catalog-only')
            if declarations.get(path) != row['original_url']:
                errors.append(f'{path}: pinned URL changed')
        elif row.get('current_disposition') == 'pinned-submodule':
            errors.append(f'{path}: unversioned reference claimed as a pinned dependency')
    return errors


def main():
    try:
        errors = validate()
    except (OSError, ValueError, KeyError, configparser.Error, subprocess.CalledProcessError) as exc:
        print(f'FAIL: dependency metadata: {exc}', file=sys.stderr)
        return 1
    for error in errors:
        print('FAIL: ' + error, file=sys.stderr)
    if errors:
        return 1
    print('OK: two pinned gitlinks; all 69 historical dependency records preserved')
    print('INFO: unversioned references are catalog entries, not restorable submodules')
    print('INFO: legacy package/source builds require their own environment validation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
