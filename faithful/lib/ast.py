"""Protocol v1 JSON representation of types, programs, grammars and frontiers.

Everything the library exchanges with the Haskell kernel is plain JSON; these
helpers only construct and inspect that JSON. See ``faithful/protocol/README.md``.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Iterable

Type = dict
Program = dict
Grammar = dict
Frontier = dict

# ---- types -----------------------------------------------------------------

def base(name: str, *arguments: Type) -> Type:
    return {"constructor": name, "arguments": list(arguments)}

def arrow(a: Type, b: Type) -> Type:
    return {"constructor": "->", "arguments": [a, b]}

def arrows(*types: Type) -> Type:
    """``arrows(a, b, c)`` is ``a -> (b -> c)``; the last entry is the result."""
    result = types[-1]
    for t in reversed(types[:-1]):
        result = arrow(t, result)
    return result

def variable(i: int) -> Type:
    return {"var": i}

def is_arrow(t: Type) -> bool:
    return t.get("constructor") == "->"

def arity(t: Type) -> int:
    return 1 + arity(t["arguments"][1]) if is_arrow(t) else 0

def argument_types(t: Type) -> list[Type]:
    out = []
    while is_arrow(t):
        out.append(t["arguments"][0]); t = t["arguments"][1]
    return out

def result_type(t: Type) -> Type:
    while is_arrow(t):
        t = t["arguments"][1]
    return t

def show_type(t: Type) -> str:
    if "var" in t: return f"t{t['var']}"
    if is_arrow(t):
        a, b = t["arguments"]
        return f"({show_type(a)} -> {show_type(b)})"
    if t["arguments"]: return t["constructor"] + "[" + ", ".join(map(show_type, t["arguments"])) + "]"
    return t["constructor"]

# ---- programs --------------------------------------------------------------

def primitive(name: str) -> Program:
    return {"primitive": name}

def index(i: int) -> Program:
    return {"index": i}

def application(f: Program, *xs: Program) -> Program:
    for x in xs:
        f = {"application": [f, x]}
    return f

def abstraction(body: Program) -> Program:
    return {"abstraction": body}

def abstractions(body: Program, n: int) -> Program:
    for _ in range(n):
        body = abstraction(body)
    return body

def invented(body: Program) -> Program:
    return {"invented": body}

def leaves(p: Program) -> int:
    """Leaf count (primitive/index/invented), the kernel's notion of program size."""
    if "application" in p: return sum(map(leaves, p["application"]))
    if "abstraction" in p: return leaves(p["abstraction"])
    return 1

def primitives_used(p: Program, expand_inventions: bool = True) -> set[str]:
    if "application" in p: return set().union(*map(lambda q: primitives_used(q, expand_inventions), p["application"]))
    if "abstraction" in p: return primitives_used(p["abstraction"], expand_inventions)
    if "invented" in p: return primitives_used(p["invented"], expand_inventions) if expand_inventions else set()
    if "primitive" in p: return {p["primitive"]}
    return set()

def show_program(p: Program) -> str:
    """DreamCoder textual form: ``(lambda (f $0))``, inventions as ``#(...)``."""
    if "application" in p:
        f, x = p["application"]
        return f"({show_program(f)} {show_program(x)})"
    if "abstraction" in p: return f"(lambda {show_program(p['abstraction'])})"
    if "invented" in p: return f"#{show_program(p['invented'])}"
    if "index" in p: return f"${p['index']}"
    return p["primitive"]

def parse_program(text: str) -> Program:
    """Inverse of :func:`show_program` (accepts ``lambda`` or ``lam``)."""
    import re
    tokens = iter(re.findall(r"\(|\)|#|[^\s()#]+", text))
    def read(token):
        if token == "#": return invented(read(next(tokens)))
        if token == "(":
            head = next(tokens)
            if head in ("lambda", "lam"):
                body = read(next(tokens))
                if next(tokens) != ")": raise ValueError("Malformed lambda")
                return abstraction(body)
            result = read(head)
            for t in tokens:
                if t == ")": return result
                result = {"application": [result, read(t)]}
            raise ValueError("Unclosed application")
        if token == ")": raise ValueError("Unexpected ')'")
        if token.startswith("$"): return index(int(token[1:]))
        return primitive(token)
    result = read(next(tokens))
    if next(tokens, None) is not None: raise ValueError("Trailing tokens")
    return result

# ---- grammars and frontiers ------------------------------------------------

def production(program: Program, type: Type, log_weight: float = 0.) -> dict:
    return {"program": program, "type": type, "log_weight": float(log_weight)}

def grammar(productions: Iterable[dict], log_variable: float = 0.) -> Grammar:
    return {"log_variable": float(log_variable), "productions": list(productions)}

def frontier(request: Type, entries: Iterable[dict] = ()) -> Frontier:
    return {"request": request, "entries": list(entries)}

def entry(program: Program, log_likelihood: float = 0., **extra: Any) -> dict:
    return {"program": program, "log_likelihood": float(log_likelihood), **extra}

def digest(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()

def program_key(p: Program) -> str:
    return json.dumps(p, sort_keys=True)
