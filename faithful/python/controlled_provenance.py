"""Record runtime and benchmark-harness sources without modifying the core."""
import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path
import torch
from .kernel import ROOT, EXE
from .controlled_run import OUT, verify
from .toy import save


def record(out=OUT):
    manifest = verify(out)
    files = list((ROOT/'faithful/python').glob('controlled_*.py')) + [ROOT/'faithful/tests/test_controlled.py',
        ROOT/'faithful/tests/test_recognition_device.py', ROOT/'faithful/python/recognition.py']
    copied = {}
    for path in files:
        destination = out/'source_snapshot'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        copied[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    save(out/'environment.json', {'python': sys.version, 'python_executable': sys.executable,
        'torch': str(torch.__version__), 'platform': platform.platform(),
        'recognition_device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'cuda_runtime': torch.version.cuda,
        'gpu_name': torch.cuda.get_device_name() if torch.cuda.is_available() else None,
        'ghc': subprocess.check_output(['ghc', '--numeric-version'], text=True).strip(),
        'kernel_executable_sha256': hashlib.sha256(EXE.read_bytes()).hexdigest(),
        'harness_sources_sha256': copied, 'runtime_variant': manifest.get('runtime_variant'),
        'source_note': 'Source snapshot for this execution. Runtime variants preserve all parent benchmark-data hashes and record their separate recognition device-placement revision.'})


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    record(parser.parse_args().output)
