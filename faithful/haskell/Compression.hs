{-# LANGUAGE FlexibleContexts #-}
module Compression where
import Syntax
import Grammar
import Json
import Data.List (nub,sort,sortOn)
import qualified Data.Set as S
import qualified Data.Map.Strict as M
import Data.Maybe (mapMaybe)
import Control.Monad.State.Strict

unique :: Ord a => [a] -> [a]
unique = S.toList . S.fromList
subterms p = p:case p of App f x->subterms f++subterms x; Lam b->subterms b; _->[]
leafSize (App f x) = leafSize f+leafSize x
leafSize (Lam b) = leafSize b
leafSize _ = 1
freeVariables = unique . go 0 where
  go d (Index i) = [i-d | i>=d]
  go d (Lam b) = go (d+1) b
  go d (App f x) = go d f++go d x
  go _ _ = []
closeFragment p = let vs=freeVariables p
                      rename d (Index i) | i>=d = Index (d+length(takeWhile (/=(i-d)) vs))
                      rename d (Lam b) = Lam(rename (d+1) b)
                      rename d (App f x) = App(rename d f)(rename d x)
                      rename _ x = x
                  in Inv(iterate Lam (rename 0 p)!!length vs)

-- Explicit finite version sets: no e-graph sharing, same inverse-beta rule.
-- Moving an extraction across n binders is permitted only if none are captured.
lower n = go 0 where
  go d (Index i) | i<d = Just(Index i)
                 | i<d+n = Nothing
                 | otherwise = Just(Index(i-n))
  go d (Lam b) = Lam <$> go (d+1) b
  go d (App f x) = App <$> go d f <*> go d x
  go _ p = Just p
substitutions n p = unique (top++children) where
  top=case lower n p of Just x->[(Just x,Index n)]; _->[]
  children=case p of
    Lam b -> [(v,Lam b') | (v,b')<-substitutions (n+1) b]
    App f x -> [(v,App f' x') | (a,f')<-substitutions n f,(b,x')<-substitutions n x,
                  v<-case (a,b) of (Nothing,z)->[z];(z,Nothing)->[z];(Just u,Just v) | u==v->[Just u];_->[]]
    Index i -> [(Nothing,Index(if i<n then i else i+1))]
    _ -> [(Nothing,p)]
inverseStep p = unique (top++below) where
  top=[App (Lam b) v | (Just v,b)<-substitutions 0 p,b/=Index 0]
  below=case p of
    App f x -> [App f' x | f'<-inverseStep f]++[App f x' | x'<-inverseStep x]
    Lam b -> map Lam(inverseStep b)
    _ -> []
betaAllowed = go False True where
  go applied allowed (Lam b) = (not applied || allowed) && go False (allowed && not applied) b
  go _ allowed (App f x) = go True allowed f && go False allowed x
  go _ _ _ = True
inlineTop p = case spine p of
  (Inv b,xs) | length xs>=fst(stripLambdas b) -> [betaOpaque(foldl App b xs)]
  _ -> []
versions n p = unique (filter betaAllowed (children++concat(take (n+1)(iterate (unique . concatMap (\q->inverseStep q++inlineTop q)) [p])))) where
  children=case p of
    App f x -> [App f' x' | f'<-versions n f,x'<-versions n x]
    Lam b -> map Lam(versions n b)
    _ -> [p]
nontrivial p = length leaves>1 || length leaves==1 && length idxs>length(nub idxs)
  where leaves=[x | x<-subterms p,case x of Prim _->True;Inv _->True;_->False]
        idxs=indices 0 p
        indices d (Index i)=[i-d]
        indices d (Lam b)=indices(d+1)b
        indices d (App f x)=indices d f++indices d x
        indices _ _=[]

-- Match a normalized invention body with free slots, preserving local binders.
matchFragment pattern target = go 0 pattern target M.empty where
  go d (Index i) q bs | i>=d = do
    v<-lower d q
    case M.lookup (i-d) bs of Nothing->Just(M.insert(i-d)v bs);Just w | w==v->Just bs;_->Nothing
  go d (Lam a) (Lam b) bs = go (d+1) a b bs
  go d (App a b) (App c e) bs = go d a c bs >>= go d b e
  go _ a b bs | a==b = Just bs
  go _ _ _ _ = Nothing
stripLambdas (Lam b) = let (n,x)=stripLambdas b in (n+1,x)
stripLambdas p = (0,p)
rewrite inv@(Inv body) p = best (normal:direct) where
  (n,pat)=stripLambdas body
  normal=case p of App f x->App(rewrite inv f)(rewrite inv x);Lam b->Lam(rewrite inv b);_->p
  direct=case matchFragment pat p of
    Just bs | all (`M.member` bs) [0..n-1] -> [foldl App inv [bs M.! i | i<-reverse[0..n-1]]]
    _ -> []
  best = snd . minimum . map (\q->((leafSize q,size q,show q),q))
rewrite _ p = p

-- Eta expansion and beta reduction of administrative redexes; inventions opaque.
betaOpaque (App f x) = case betaOpaque f of Lam b->betaOpaque(shift (-1) 0(subst 0 (shift 1 0 x)b));q->App q(betaOpaque x)
betaOpaque (Lam b)=Lam(betaOpaque b)
betaOpaque p=p
etaLong g req expr = runTI (go [] req (betaOpaque expr)) where
  go env t p = do
    r<-resolve t
    case r of
      TC "->" [a,b] -> case p of
        Lam body -> Lam <$> go (a:env) b body
        _ -> go env r (Lam(App(shift 1 0 p)(Index 0)))
      _ -> do
        let (h,xs)=spine p
        ht<-infer (signature g) env h
        unify (returns ht) r
        args<-sequence [go env a x | (a,x)<-zip(arguments ht) xs]
        if length xs/=length(arguments ht) then lift(Left "Eta arity") else pure(foldl App h args)

objective g fs pc aic penalty = do
  fitted<-insideOutside g fs pc 1
  values<-mapM (frontier fitted) fs
  let complexity=sum [case term p of Inv b->leafSize b;_->1 | p<-productions fitted]
  pure(fitted,sum(map fst values)-aic*fromIntegral(length(productions g))-penalty*fromIntegral complexity)

-- Candidates come from subterms of inverse-beta versions, closed over all
-- free variables. Multiple invented productions may be added per call.
compressionCandidates g fs n =
  let byTask=[S.fromList [inv | (p,_)<-es,v<-versions n p,s<-subterms v,nontrivial s,betaOpaque s==s,
                  let inv=closeFragment s,Right _<-[typeOf(signature g)[]inv]] | (_,es)<-fs]
      support=M.fromListWith (+) [(p,1::Int) | set<-byTask,p<-S.toList set]
  in [p | (p,c)<-M.toList support,c>=2,p `notElem` map term(productions g)]
compress g fs n rounds pc aic penalty = loop g fs rounds [] where
  loop g fs 0 history = Right(g,fs,reverse history)
  loop g fs remaining history = do
    (base,old)<-objective g fs pc aic penalty
    let cs=compressionCandidates g fs n
        trial inv = do
          tp<-typeOf(signature g)[]inv
          let uniform=Grammar 0 (map (\pr->pr{weight=0})(productions g)++[Production inv tp 0]) []
          rewritten<-mapM (\(r,es)->do
            es'<-mapM (\(p,ll)->do
              let alternatives=[q | v<-versions n p,Right q<-[etaLong uniform r(rewrite inv v)],beta q==beta p,
                                    Right _<-[summary uniform [] r q]]
                  q=if null alternatives then p else snd(minimum [((leafSize q,size q,show q),q) | q<-alternatives])
              pure(q,ll)) es
            pure(r,es')) fs
          (fitted,s)<-objective uniform rewritten pc aic penalty
          pure(s,fitted,rewritten,inv)
        trials=[x | Right x<-map trial cs]
    case sortOn (\(s,_,_,p)->(-s,show p)) trials of
      (s,g',fs',p):_ | s>old+1e-10 -> loop g' fs' (remaining-1) (Obj[("before",Num old),("after",Num s),("invented",progJ p),("candidate_count",Num(fromIntegral(length cs)))]:history)
      _ -> Right(base,fs,reverse history)
frontierInputJ (r,es) = Obj[("request",typeJ r),("entries",Arr[Obj[("program",progJ p),("log_likelihood",Num ll)] | (p,ll)<-es])]
