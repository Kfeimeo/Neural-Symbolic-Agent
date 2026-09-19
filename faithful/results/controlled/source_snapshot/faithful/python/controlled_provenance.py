"""Record runtime and benchmark-harness sources without modifying the core."""
import hashlib
import platform
import shutil
import subprocess
import sys
import torch
from .kernel import ROOT, EXE
from .controlled_run import OUT, verify
from .toy import save


def record(out=OUT):
    verify(out)
    files = list((ROOT/'faithful/python').glob('controlled_*.py')) + [ROOT/'faithful/tests/test_controlled.py']
    copied = {}
    for path in files:
        destination = out/'source_snapshot'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        copied[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    save(out/'environment.json', {'python': sys.version, 'python_executable': sys.executable,
        'torch': str(torch.__version__), 'platform': platform.platform(), 'recognition_device': 'cpu',
        'ghc': subprocess.check_output(['ghc', '--numeric-version'], text=True).strip(),
        'kernel_executable_sha256': hashlib.sha256(EXE.read_bytes()).hexdigest(),
        'harness_sources_sha256': copied, 'source_note': 'Final harness source snapshot. Post-freeze changes were evaluation batching, audits, report generation and regression tests; no benchmark regeneration or core edits.'})


if __name__ == '__main__': record()
