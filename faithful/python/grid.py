"""Grid domain boundary: data, primitive signatures, request, encoder."""
from dataclasses import dataclass
import torch
from .kernel import base,arrow,primitive

GRID=base("grid")
COLOR,INT,BOOL,OBJECT,OBJECTS=map(base,("color","int","bool","object","objects"))
REQUEST=arrow(GRID,GRID)
def smoke_grammar():
    return {"log_variable":0.,"productions":[{"program":primitive(n),"type":REQUEST,"log_weight":0.} for n in ("rotate90","flipH","flipV","transpose","invert")]}

def grammar():
    specs=[("identity",[GRID],GRID),("rotate90",[GRID],GRID),("rotate180",[GRID],GRID),
           ("flipH",[GRID],GRID),("flipV",[GRID],GRID),("transpose",[GRID],GRID),
           ("trim",[GRID],GRID),("invert",[GRID],GRID),("recolor",[GRID,COLOR,COLOR],GRID),
           ("objects",[GRID],OBJECTS),("largest",[OBJECTS],OBJECT),("crop",[OBJECT],GRID),
           ("translate",[GRID,INT,INT],GRID),("count",[OBJECTS],INT),("is_empty",[OBJECTS],BOOL),
           ("if_grid",[BOOL,GRID,GRID],GRID),("border",[GRID],GRID),("solid",[GRID,COLOR],GRID)]
    specs += [(n,[],t) for n,t in [("red",COLOR),("blue",COLOR),("green",COLOR),("zero",INT),("one",INT),("minus_one",INT)]]
    productions=[]
    for name,args,result in specs:
        for a in reversed(args):result=arrow(a,result)
        productions.append({"program":primitive(name),"type":result,"log_weight":0.})
    return {"log_variable":0.,"productions":productions}

@dataclass
class Task:
    name: str
    examples: list
    request: dict = None
    def __post_init__(self):
        if self.request is None: self.request=REQUEST
    # Deliberately no ground-truth field in the learner's Task type.

def features(task):
    rows=[]
    for inputs,output in task.examples:
        vector=[]
        for grid in (inputs[0],output):
            flat=[c for row in grid for c in row]
            vector.extend([len(grid)/10,len(grid[0])/10]+[flat.count(c)/len(flat) for c in range(4)])
            vector.extend([(grid[y][x]/3 if y<len(grid) and x<len(grid[0]) else -1) for y in range(2) for x in range(7)])
        rows.append(vector)
    return torch.tensor(rows,dtype=torch.float32).mean(0)
