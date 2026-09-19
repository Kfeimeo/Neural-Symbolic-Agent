import json,re,subprocess,sys
from faithful.python.kernel import *

def probe():
    out=ROOT/"faithful/results";report={}
    with Kernel() as k:
        for name in ("compression","hierarchy"):
            fixture=json.loads((out/f"{name}_fixture.json").read_text())
            strings=re.findall(r"^Invention (.+) : .+$",(out/f"{name}_official.log").read_text(),re.M)
            r=subprocess.run([sys.executable,str(ROOT/"faithful/tests/oracle.py")],input=json.dumps(dict(operation="parse_programs",grammar=fixture["grammar"],programs=strings))+"\n",capture_output=True,text=True,check=True)
            result=json.loads(r.stdout)
            if not result["ok"]:raise RuntimeError(result)
            official=result["result"]["programs"]
            ours=k.call("compression_candidates",**fixture,arity=1)["programs"]
            key=lambda p:json.dumps(p,sort_keys=True)
            a,b=set(map(key,ours)),set(map(key,official))
            existing={key(p["program"]) for p in fixture["grammar"]["productions"]}
            beta_key=lambda p:key(k.call("beta",program=p)["program"])
            ba={beta_key(p) for p in ours}
            bb={beta_key(p) for p in official if key(p) not in existing}
            report[name]={"ours":len(a),"official_normalized":len(b),"ours_only":[json.loads(x) for x in sorted(a-b)],"official_only":[json.loads(x) for x in sorted(b-a)],"beta_classes_ours":len(ba),"beta_classes_official":len(bb),"beta_classes_equal":ba==bb}
    (out/"candidate_comparison.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print({n:{k:len(v) if isinstance(v,list) else v for k,v in d.items()} for n,d in report.items()})
    return report
if __name__=="__main__":probe()
