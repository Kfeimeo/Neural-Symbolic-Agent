"""Parser for the printed term syntax, e.g.

    (map (λObject. (translate $0 down)) $0)
    (#f0 right $0)

``λ`` may be written ``\\`` or ``lambda``; the parameter type is optional and
defaults to Object.  Used by tests, traces and the diagnostic tool."""
from __future__ import annotations

import re

from ..ml.types import Type
from .ast import Abs, App, Prim, Term, Var

_TOKEN = re.compile(r"\(|\)|[^\s()]+")


def parse_term(text: str, default_param: Type = Type("Object")) -> Term:
    tokens = _TOKEN.findall(text)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def read() -> Term:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            head = tokens[pos]
            pos += 1
            if head.startswith("λ") or head.startswith("\\") or head.startswith("lambda"):
                name = head.lstrip("λ\\")
                if name.startswith("lambda"):
                    name = name[len("lambda"):]
                name = name.rstrip(".")
                typ = Type(name) if name else default_param
                body = read()
                if peek() != ")":
                    raise ValueError("expected ) after lambda body")
                pos += 1
                return Abs(typ, body)
            args = []
            while peek() != ")":
                if peek() is None:
                    raise ValueError("unbalanced parentheses")
                args.append(read())
            pos += 1
            return App(head, tuple(args)) if args else Prim(head)
        if tok == ")":
            raise ValueError("unexpected )")
        if tok.startswith("$"):
            return Var(int(tok[1:]))
        return Prim(tok)

    term = read()
    if pos != len(tokens):
        raise ValueError("trailing tokens")
    return term
