"""Task-conditioned AST bigram grammar and DreamCoder frontier objectives."""
import copy
import os
import random

# Required by deterministic CUDA matmul; configure before a CUDA BLAS handle is
# created. Keep an explicit user setting (including :16:8) intact.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch
from torch import nn

def arity(t):
    return 1+arity(t["arguments"][1]) if t.get("constructor")=="->" else 0

def context_keys(grammar):
    return ["root","variable"]+[f"{i}:{a}" for i,p in enumerate(grammar["productions"],1) for a in range(arity(p["type"]))]

def program_log_probability(logits, events, keys):
    """Differentiable typed probability; events come exclusively from Haskell."""
    rows={k:i for i,k in enumerate(keys)}
    terms=[]
    for e in events:
        w=logits[rows[e["context"]]]
        terms.append(w[e["actual"]]-torch.logsumexp(w[e["possible"]],0)+e["constant"])
    return torch.stack(terms).sum() if terms else logits.sum()*0

def frontier_bias_optimal(logits, summaries, likelihoods, keys):
    return -torch.stack([program_log_probability(logits,s,keys)+ll for s,ll in zip(summaries,likelihoods)]).max()

def frontier_kl(logits,summaries,posterior,keys):
    """Exact expectation of official posterior-sampled NLL (entropy omitted)."""
    return -sum(w*program_log_probability(logits,s,keys) for w,s in zip(posterior,summaries))

def replay_sample(frontier,rng):
    return rng.choices(frontier["entries"],weights=[e["posterior"] for e in frontier["entries"]],k=1)[0]

class Recognition(nn.Module):
    def __init__(self,grammar,feature_dim=40,hidden=64,device=None):
        super().__init__()
        self.grammar=copy.deepcopy(grammar)
        self.keys=context_keys(grammar)
        self.encoder=nn.Sequential(nn.Linear(feature_dim,hidden),nn.Tanh())
        self.head=nn.Linear(hidden,len(self.keys)*(len(grammar["productions"])+1))
        self.to(device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu"))
    @property
    def device(self):
        return next(self.parameters()).device
    def forward(self,features):
        features=features.to(self.device)
        return self.head(self.encoder(features)).reshape(len(self.keys),len(self.grammar["productions"])+1)
    def search_grammar(self,features):
        g=copy.deepcopy(self.grammar)
        with torch.no_grad(): g["contexts"]=dict(zip(self.keys,self(features).cpu().tolist()))
        return g
    def fit_frontiers(self,kernel,data,steps=50,seed=0,objective="bias_optimal"):
        rng=random.Random(seed)
        prepared=[]
        for features,frontier in data:
            if not frontier["entries"]: continue
            scored=kernel.call("frontier",grammar=self.grammar,frontier=frontier)
            summaries=[kernel.call("score",grammar=self.grammar,request=frontier["request"],program=e["program"])["events"] for e in scored["entries"]]
            prepared.append((features.to(self.device),scored,summaries))
        if not prepared: return []
        optimizer=torch.optim.Adam(self.parameters(),lr=.001)
        history=[]
        for _ in range(steps):
            features,f,s=rng.choice(prepared); logits=self(features)
            if objective=="bias_optimal":
                loss=frontier_bias_optimal(logits,s,[e["log_likelihood"] for e in f["entries"]],self.keys)
            elif objective=="kl":
                i=rng.choices(range(len(s)),weights=[e["posterior"] for e in f["entries"]],k=1)[0]
                loss=-program_log_probability(logits,s[i],self.keys)
            else: raise ValueError(objective)
            optimizer.zero_grad();loss.backward();optimizer.step();history.append(float(loss.detach()))
        return history
