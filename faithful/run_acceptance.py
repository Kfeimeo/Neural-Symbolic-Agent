"""Rebuild, regenerate live reference evidence, then run both test suites."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from faithful.python.kernel import ROOT,build,Kernel
from faithful.tests.compression_fixture import fixture,official_input
from faithful.tests.hierarchy_probe import hierarchy_fixture

COMMIT="cb0e63f5c33cd2de360b791038b0f5272750270e"
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    reference=ROOT/"faithful/reference/ec"
    commit=subprocess.check_output(["git","-C",str(reference),"rev-parse","HEAD"],text=True).strip()
    if commit!=COMMIT:raise RuntimeError("Official reference commit changed")
    if subprocess.check_output(["git","-C",str(reference),"diff","--name-only"],text=True).strip():
        raise RuntimeError("Official tracked source was modified")
    build()
    out=ROOT/"faithful/results";out.mkdir(exist_ok=True)
    provenance={"commit":commit,"reference_files":{str(p.relative_to(reference)):sha(p) for p in [reference/"dreamcoder"/n for n in ("type.py","program.py","grammar.py","frontier.py","recognition.py")]+[reference/"compression",reference/"solvers/compression.ml",reference/"solvers/versions.ml"]}}
    with Kernel() as k:
        for name in ("compression","hierarchy"):
            g,fs=fixture() if name=="compression" else hierarchy_fixture(k)
            input_path=out/f"{name}_input.json"
            input_path.write_text(json.dumps(official_input(g,fs)),encoding="utf8")
            response=k.call("compress",grammar=g,frontiers=fs,arity=1,iterations=1)
            (out/f"{name}_ours.json").write_text(json.dumps(response,indent=2),encoding="utf8")
            (out/f"{name}_fixture.json").write_text(json.dumps({"grammar":g,"frontiers":fs}),encoding="utf8")
            # Paths are fixed trusted workspace paths, not interpolated user code.
            linux_ref="/mnt/"+str(reference)[0].lower()+str(reference)[2:].replace("\\","/")
            command=f'cd "{linux_ref}" && ./compression ../../results/{name}_input.json'
            result=subprocess.run(["wsl","-d","Ubuntu-24.04","--","sh","-c",command],capture_output=True,text=True,check=True,timeout=120)
            (out/f"{name}_official.json").write_text(result.stdout,encoding="utf8")
            (out/f"{name}_official.log").write_text(result.stderr,encoding="utf8")
            provenance[name]={"input_sha256":sha(input_path),"output_sha256":sha(out/f"{name}_official.json")}
    trace=out/"golden_trace.jsonl";trace.write_text("",encoding="utf8")
    env=dict(os.environ,FAITHFUL_TRACE=str(trace))
    result=subprocess.run([sys.executable,"-m","pytest","faithful/tests","tests","-q","-p","no:cacheprovider","--junitxml="+str(out/"junit.xml")],cwd=ROOT,env=env)
    provenance["test_exit_code"]=result.returncode
    provenance["trace_sha256"]=sha(trace)
    provenance["implementation_files"]={str(p.relative_to(ROOT)):sha(p) for root in (ROOT/"faithful/haskell",ROOT/"faithful/python",ROOT/"faithful/tests") for p in root.rglob("*") if p.suffix in (".hs",".py")}
    (out/"provenance.json").write_text(json.dumps(provenance,indent=2),encoding="utf8")
    raise SystemExit(result.returncode)
if __name__=="__main__":main()
