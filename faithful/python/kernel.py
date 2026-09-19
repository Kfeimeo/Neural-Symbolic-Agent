"""Version 1 newline-delimited JSON client. No symbolic Python fallback."""
from pathlib import Path
import json
import subprocess
import os

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / "faithful" / "build" / "kernel.exe"

def build():
    EXE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ghc", "-O1", "-i" + str(ROOT / "faithful/haskell"),
                    "-outputdir", str(EXE.parent), str(ROOT / "faithful/haskell/Main.hs"),
                    "-o", str(EXE)], check=True, cwd=ROOT)

class Kernel:
    def __init__(self):
        self.process = subprocess.Popen([str(EXE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, encoding="utf-8")
    def call(self, operation, **payload):
        request=dict(version=1, operation=operation, **payload)
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        if os.environ.get("FAITHFUL_TRACE"):
            with open(os.environ["FAITHFUL_TRACE"],"a",encoding="utf8") as f:
                f.write(json.dumps({"implementation":"haskell","request":request,"response":response})+"\n")
        if not response["ok"]:
            raise ValueError(response["error"])
        return response["result"]
    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

def base(name): return {"constructor": name, "arguments": []}
def arrow(a, b): return {"constructor": "->", "arguments": [a, b]}
def variable(i): return {"var": i}
def primitive(name): return {"primitive": name}
def index(i): return {"index": i}
def application(f, *xs):
    for x in xs: f = {"application": [f, x]}
    return f
def abstraction(body): return {"abstraction": body}
def invented(body): return {"invented": body}

if __name__ == "__main__": build()
