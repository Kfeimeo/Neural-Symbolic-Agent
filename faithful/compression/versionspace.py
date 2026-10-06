"""Shared version-space compressor (port of the reference OCaml algorithm).

The kernel is a superset of the frozen one: `vs_compress`, `vs_candidates` and
`vs_versions` are added, every other operation is served unchanged.
"""
import subprocess
from ..python.kernel import Kernel, ROOT
from .interface import Compressor

EXE = ROOT/'faithful/build/versionspace_kernel.exe'

def build_versionspace():
    folder = ROOT/'faithful/build/versionspace'
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ghc', '-O1', '-i'+str(ROOT/'faithful/haskell'), '-i'+str(ROOT/'faithful/compression'),
        '-i'+str(ROOT/'faithful/versionspace'), '-outputdir', str(folder), '-main-is', 'VSMain.main',
        str(ROOT/'faithful/versionspace/VSMain.hs'), '-o', str(EXE)], check=True)

class VersionSpaceKernel(Kernel):
    """With `compress_options` (possibly empty), the frozen drivers' `compress`
    requests are answered by `vs_compress`, so an unmodified EC loop can be run
    on the shared table by substituting this class for `Kernel`."""
    def __init__(self, compress_options=None):
        self.process = subprocess.Popen([str(EXE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf8')
        self.compress_options = compress_options
    def call(self, operation, **payload):
        if operation == 'compress' and self.compress_options is not None:
            r = super().call('vs_compress', **{**payload, **self.compress_options})
            return {key: r[key] for key in ('grammar', 'frontiers', 'history')}
        return super().call(operation, **payload)

class VersionSpaceCompressor(Compressor):
    """Requires a VersionSpaceKernel. Options are the reference's: arity,
    top_k (frontier restriction), top_i (candidates rescored), beam_size,
    inline, and likelihood ('ocaml' selects the reference normaliser)."""
    def __init__(self, kernel, iterations=3, **options):
        super().__init__(kernel, iterations)
        self.options = dict(dict(arity=1), **options)
    def _compress(self, frontier, grammar):
        r = self.kernel.call('vs_compress', grammar=grammar, frontiers=frontier, iterations=self.iterations, **self.options)
        stats = {'backend': 'versionspace', 'options': self.options, 'final_step': r['final_step']}
        return self.result(frontier, grammar, r['grammar'], r['frontiers'], r['history'], stats)

if __name__ == '__main__': build_versionspace()
