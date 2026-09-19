{-# LANGUAGE FlexibleContexts #-}
module Grammar where
import Syntax
import Json
import qualified Data.Map.Strict as M
import Data.List (nub,sortOn)
import Control.Monad.State.Strict
import Data.Maybe (mapMaybe)

data Production = Production { term::P, scheme::Type, weight::Double } deriving Show
data Grammar = Grammar { variableWeight::Double, productions::[Production], contexts::[(String,[Double])] } deriving Show
data Event = Event { location::String, actual::Int, possible::[Int], constant::Double } deriving Show
type Ctx = (Int,Sub)
data Candidate = Candidate P Type Ctx Int Double deriving Show
lse [] = -1/0
lse xs = let m=maximum xs in if isInfinite m then m else m+log(sum(map (exp . subtract m) xs))
signature g = [(n,t) | Production (Prim n) t _ <- productions g]
weights g loc = maybe (variableWeight g:map weight (productions g)) id (lookup loc (contexts g))
child (Index _) _ _ = "variable"
child p i g = case [j | (j,pr)<-zip [1..] (productions g),term pr==p] of
  j:_ -> show j++":"++show i
  _ -> error "Parent outside grammar"
candidates g loc request env ctx =
  let attempt t p k instantiateIt = case runStateT (do t'<-if instantiateIt then instantiate t else pure t; unify (returns t') request; resolve t') ctx of
        Left _ -> Nothing
        Right (t',c') -> Just (p,t',c',k)
      ps=mapMaybe (\(k,pr)->attempt (scheme pr) (term pr) k True) (zip [1..] (productions g))
      vs=mapMaybe (\(i,t)->attempt t (Index i) 0 False) (zip [0..] env)
      ws=weights g loc
      raw=[(p,t,c,k,ws!!k - if k==0 then log(fromIntegral(length vs)) else 0) | (p,t,c,k)<-ps++vs]
      z=lse [w | (_,_,_,_,w)<-raw]
  in [Candidate p t c k (w-z) | (p,t,c,k,w)<-raw]

summary g env request p = fmap fst (runStateT (go "root" env request p) (initialContext(request:env))) where
  go loc env req expr = do
    r<-resolve req
    case (r,expr) of
      (TC "->" [a,b],Lam body) -> go loc (a:env) b body
      (TC "->" _,_) -> lift (Left "Arrow request requires eta-long lambda")
      _ -> do
        ctx<-get
        let cs=candidates g loc r env ctx
            (h,xs)=spine expr
        case [c | c@(Candidate q _ _ _ _)<-cs,q==h] of
          [] -> lift (Left ("Illegal head "++show h++" for "++show r))
          Candidate _ t c k _: _ -> do
            let ts=arguments t
                poss=nub [j | Candidate _ _ _ j _<-cs]
                nv=length [() | Candidate _ _ _ 0 _<-cs]
                e=Event loc k poss (if k==0 then -log(fromIntegral nv) else 0)
            if length ts/=length xs then lift (Left "Non-saturated application") else pure ()
            put c
            es<-sequence [go (child h i g) env a x | (i,(a,x))<-zip [0..] (zip ts xs)]
            pure (e:concat es)
score g es = sum [let ws=weights g loc in c+ws!!k-lse [ws!!j | j<-ks] | Event loc k ks c<-es]
logProbability g env req p = score g <$> summary g env req p

-- Complete bounded enumeration. Bounds prune derivations, never renormalize them.
-- The reference DFS is sorted by exact cost to compare ordering modulo ties.
enumerate g env req bound depth = sortOn (\(l,p)->(-l,show p)) [(l,p) | (l,_,p)<-go "root" (initialContext(req:env)) env req bound depth] where
  go loc ctx env r b d
    | b<0 || d<=1 = []
    | otherwise = case apply (snd ctx) r of
        TC "->" [a,z] -> [(l,c,Lam p) | (l,c,p)<-go loc ctx (a:env) z b d]
        t -> [(l+al,c,p) | Candidate h ht hc _ l<-candidates g loc t env ctx,-l<b,
                           (al,c,p)<-args h 0 hc env h (arguments ht) (b+l) (d-1)]
  args original i ctx env f ts b d
    | b<0 || d<=1 = []
    | null ts = [(0,ctx,f) | 0<b]
    | otherwise = [(l+al,c,p) | (l,c1,x)<-go (child original i g) ctx env (head ts) b d,
                                (al,c,p)<-args original (i+1) c1 env (App f x) (tail ts) (b+l) d]

-- Frontiers carry likelihoods, and are always rescored with the generative G.
type Frontier = (Type,[(P,Double)])
frontier g (r,entries) = do
  ls<-mapM (\(p,ll)->do lp<-logProbability g [] r p; pure (p,lp,ll)) entries
  let z=lse [lp+ll | (_,lp,ll)<-ls]
  pure (z,[(p,lp,ll,lp+ll-z) | (p,lp,ll)<-ls])
insideOutside g fs pc iterations
  | pc<=0 = Left "pseudo_counts must be positive"
  | iterations<=0 = Right g
  | otherwise = do
      rows<-mapM perFrontier fs
      let observations=concat rows
          indices=[0..length(productions g)]
          act k=sum [w | (w,es)<-observations,e<-es,actual e==k]
          poss k=sum [w | (w,es)<-observations,e<-es,k `elem` possible e]
          ws=[log(act k+pc)-log(poss k+pc) | k<-indices]
          g'=Grammar (head ws) (zipWith (\p w->p{weight=w}) (productions g) (tail ws)) []
      insideOutside g' fs pc (iterations-1)
  where perFrontier (r,entries) = do
          es<-mapM (\(p,ll)->do s<-summary g [] r p; pure (s,ll+score g s)) entries
          let z=lse (map snd es)
          pure [(exp(l-z),s) | (s,l)<-es]
readG j = Grammar (num (field "log_variable" j))
  [Production (readP(field "program" p)) (readType(field "type" p)) (num(field "log_weight" p)) | p<-arr(field "productions" j)]
  (case field "contexts" j of Obj xs -> [(k,map num(arr v)) | (k,v)<-xs]; _->[])
grammarJ g = Obj [("log_variable",Num(variableWeight g)),("productions",Arr [Obj [("program",progJ(term p)),("type",typeJ(scheme p)),("log_weight",Num(weight p))] | p<-productions g]),("contexts",Obj [(k,Arr(map Num ws)) | (k,ws)<-contexts g])]
eventJ (Event loc k ks c) = Obj [("context",Str loc),("actual",Num(fromIntegral k)),("possible",Arr(map (Num . fromIntegral) ks)),("constant",Num c)]
-- Uniform randomness is supplied by the caller; resource exhaustion is a
-- failed draw, never a forced leaf or renormalized terminal distribution.
sampleProgram g env req uniforms = do
  (p,_,_,_)<-go "root" (initialContext(req:env)) env req uniforms
  pure p
  where
    go loc ctx env r us = case apply (snd ctx) r of
      TC "->" [a,b] -> do (p,c,vs,n)<-go loc ctx (a:env) b us; pure(Lam p,c,vs,n)
      t -> case us of
        [] -> Left "Sample resource exhausted"
        u:rest | u<0 || u>=1 -> Left "Uniform must be in [0,1)"
               | otherwise -> do
          let cs=candidates g loc t env ctx
              pick _ [] = Nothing
              pick x (c@(Candidate _ _ _ _ l):xs) = if x<exp l then Just c else pick (x-exp l) xs
          case pick u cs of
            Nothing -> Left "No candidate in sample"
            Just (Candidate h ht hc _ _) -> args h 0 hc env h (arguments ht) rest
    args _ _ ctx _ f [] us = Right(f,ctx,us,())
    args h i ctx env f (t:ts) us = do
      (x,c,vs,_)<-go (child h i g) ctx env t us
      args h (i+1) c env (App f x) ts vs
readFrontier j = (readType(field "request" j),[(readP(field "program" e),num(field "log_likelihood" e)) | e<-arr(field "entries" j)])
frontierJ (z,es) = Obj [("log_marginal",Num z),("entries",Arr [Obj [("program",progJ p),("log_prior",Num lp),("log_likelihood",Num ll),("log_posterior",Num post),("posterior",Num(exp post))] | (p,lp,ll,post)<-es])]
