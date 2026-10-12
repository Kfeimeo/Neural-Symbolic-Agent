"""Syntactic structure keys; equal observations are not semantic proofs."""
from ..ml.ast import Abs, App, Prim, Var


def structure_key(term, library):
    """Keep operators/binding structure; erase nullary base literal values.

    Color or integer literal substitutions alone do not constitute a new
    structure. Invented production identities are retained.
    """
    if isinstance(term, Var):
        return ("var", term.index)
    if isinstance(term, Abs):
        return ("lambda", str(term.param_type), structure_key(term.body, library))
    if isinstance(term, App):
        return ("app", term.name, tuple(structure_key(a, library) for a in term.args))
    if isinstance(term, Prim):
        if library.is_invented(term.name):
            return ("invented", term.name)
        return ("literal", str(library.signature(term.name)[1]))
    raise TypeError(term)
