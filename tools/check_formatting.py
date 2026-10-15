#!/usr/bin/env python3
"""Check changed first-party text, never reformat or inspect private runtime files."""
import argparse
from pathlib import PurePosixPath
import re
import subprocess
import sys

EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
EXCLUDED_PARTS = {'thirdparty', 'node_modules', '.venv', 'vendor', 'dist', 'target', 'build', '__pycache__'}
EXCLUDED_ROOTS = ('python/projects/py-academic/',)


def git(*args):
    return subprocess.check_output(['git', *args], stderr=subprocess.PIPE)


def resolve(ref):
    if ref == EMPTY_TREE:
        return ref
    return git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()


def excluded(path):
    p = PurePosixPath(path)
    return (bool(set(p.parts) & EXCLUDED_PARTS) or path.startswith(EXCLUDED_ROOTS)
            or p.suffix in {'.ipynb', '.lock'}
            or p.name in {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'robin_hood_map.h'})


def check(base=None, head=None):
    if bool(base) != bool(head):
        raise ValueError('--base and --head must be supplied together')
    if base:
        revisions = [resolve(base), resolve(head)]
        content_ref = revisions[1]
    else:
        revisions = ['--cached']
        content_ref = ''
    common = ['--no-ext-diff', '--no-textconv', '--no-renames']
    paths = git('diff', *common, '--name-only', '-z', '--diff-filter=ACMT', *revisions, '--').decode().split('\0')
    entries = git('ls-tree', '-r', '-z', content_ref) if content_ref else git('ls-files', '-s', '-z')
    modes = {}
    for entry in entries.decode().rstrip('\0').split('\0'):
        if entry:
            metadata, name = entry.split('\t', 1)
            modes[name] = metadata.split()[0]
    errors = []
    for path in filter(None, paths):
        if excluded(path):
            continue
        obj = content_ref + ':' + path
        if modes.get(path) == '160000':
            continue  # Skip gitlinks without requiring their objects locally.
        data = git('show', obj)
        if b'\0' in data:
            continue
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(f'{path}: first-party changed text is not UTF-8')
            continue
        if data and not data.endswith(b'\n'):
            errors.append(f'{path}: missing final newline')
        if PurePosixPath(path).suffix.lower() not in {'.bat', '.cmd'} and b'\r' in data:
            errors.append(f'{path}: use LF line endings')
        patch = git('diff', *common, '--no-color', '--unified=0', *revisions, '--', path)
        in_hunk = False
        for line in patch.split(b'\n'):
            if line.startswith(b'@@ '):
                in_hunk = True
                continue
            if not in_hunk or not line.startswith(b'+'):
                continue
            added = line[1:].removesuffix(b'\r')
            trailing = added[len(added.rstrip(b' \t')):]
            hard_break = path.lower().endswith('.md') and trailing == b'  ' and bool(added.rstrip())
            if trailing and not hard_break:
                errors.append(f'{path}: added line has trailing whitespace')
            if re.match(rb' +\t', added):
                errors.append(f'{path}: added indentation has spaces before a tab')
    return sorted(set(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    parser.add_argument('--head')
    args = parser.parse_args()
    try:
        errors = check(args.base, args.head)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'Formatting check could not read the requested Git comparison: {exc}', file=sys.stderr)
        return 2
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print('Changed first-party text formatting checks passed.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
