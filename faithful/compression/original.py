from .interface import Compressor

class OriginalCompressor(Compressor):
    def _compress(self, frontier, grammar):
        r=self.kernel.call('compress',grammar=grammar,frontiers=frontier,arity=1,iterations=self.iterations)
        return self.result(frontier,grammar,r['grammar'],r['frontiers'],r['history'],{'backend':'original'})
