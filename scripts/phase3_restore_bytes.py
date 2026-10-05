"""Restore only line-ending differences that exactly match frozen SHA-256 values.

Standard-library only. Preflight every file before writing anything. Never
changes code tokens, budgets, results, or expected hashes. Use --apply to write.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Path escapes repository: {name}')
    return path


def expected_hashes(root, protocol):
    expected = {}
    def add(name, value):
        name = inside(root, name).relative_to(root).as_posix()
        if name in expected and expected[name] != value:
            raise ValueError(f'Conflicting frozen hashes: {name}')
        expected[name] = value
    for name, value in json.loads(protocol.read_text(encoding='utf8'))['source_hashes'].items():
        add(name, value)
    for sums in sorted((root/'benchmarks/latent_abstraction/data').glob('seed_*/SHA256SUMS.json')):
        for name, value in json.loads(sums.read_text(encoding='utf8')).items():
            add((sums.parent/name).relative_to(root), value)
        manifest = json.loads((sums.parent/'manifest.json').read_text(encoding='utf8'))
        for name, value in manifest['core_sha256'].items():
            add(name, value)
    return expected


def restore(root, expected, apply=False):
    root = Path(root).resolve()
    changes, errors = [], []
    for name, wanted in sorted(expected.items()):
        path = inside(root, name)
        if not path.is_file():
            errors.append(f'{name}: missing')
            continue
        raw = path.read_bytes()
        if digest(raw) == wanted:
            continue
        lf = raw.replace(b'\r\n', b'\n')
        matches = [candidate for candidate in (lf, lf.replace(b'\n', b'\r\n')) if digest(candidate) == wanted]
        if not matches:
            errors.append(f'{name}: not a line-ending-only difference; use the matching source revision')
            continue
        changes.append((path, raw, matches[0]))
    if errors:
        raise ValueError('No files written.\n' + '\n'.join(errors))
    if apply:
        if any(path.read_bytes() != raw for path, raw, _ in changes):
            raise ValueError('Files changed during preflight; no files written')
        for path, _, data in changes:
            path.write_bytes(data)
    return [path.relative_to(root).as_posix() for path, _, _ in changes]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', default='results/equivalence_abstraction/protocol.json')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol = inside(root, args.protocol)
    changed = restore(root, expected_hashes(root, protocol), args.apply)
    print(json.dumps({'applied': args.apply, 'line_ending_files': changed, 'count': len(changed)}, indent=2))


if __name__ == '__main__':
    main()
