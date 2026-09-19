module Agenda where
import Syntax
import Grammar
import qualified Data.Map.Strict as M

-- Uniform-cost search over leftmost typed holes. Unification substitutions are
-- shared across siblings. Every prefix cost is a lower bound on its completions.
data Tree = Leaf P | Hole Type [Type] String Int | Lambda Tree | Apply Tree Tree deriving Show
complete (Leaf p)=Just p
complete (Hole _ _ _ _)=Nothing
complete (Lambda b)=Lam <$> complete b
complete (Apply f x)=App <$> complete f <*> complete x
lowerSize (Leaf _)=1
lowerSize (Hole _ _ _ _)=1
lowerSize (Lambda b)=lowerSize b
lowerSize (Apply f x)=lowerSize f+lowerSize x
expand g ctx (Hole r env loc depth)
  | depth<=1=[]
  | otherwise=case apply (snd ctx) r of
      TC "->" [a,b]->[(0,ctx,Lambda(Hole b (a:env) loc depth))]
      t | depth>2 -> [(-l,c,foldl Apply (Leaf h) [Hole a env (child h i g) (depth-1) | (i,a)<-zip[0..](arguments ht)]) | Candidate h ht c _ l<-candidates g loc t env ctx]
      _ -> []
expand g ctx (Lambda b)=[(c,s,Lambda b') | (c,s,b')<-expand g ctx b]
expand g ctx (Apply f x)=case complete f of
  Nothing->[(c,s,Apply f' x) | (c,s,f')<-expand g ctx f]
  Just _->[(c,s,Apply f x') | (c,s,x')<-expand g ctx x]
expand _ _ (Leaf _)=[]

budgetEnumeration g env req bound depth maxSize maxNodes maxStates =
  loop (M.singleton (0,0::Int) (Hole req env "root" depth,initialContext(req:env))) 1 0 0 [] where
  loop queue serial states emitted results
    | emitted>=maxNodes=(reverse results,states,"candidate_budget")
    | states>=maxStates=(reverse results,states,"state_budget")
    | otherwise=case M.minViewWithKey queue of
      Nothing->(reverse results,states,"exhausted_bounds")
      Just (((cost,_),(tree,ctx)),rest)->case complete tree of
        Just p->loop rest serial (states+1) (emitted+1) ((-cost,p,states+1):results)
        Nothing->let choices=[((cost+dc,serial+i),(t,s)) | (i,(dc,s,t))<-zip[0..](expand g ctx tree),cost+dc<bound,lowerSize t<=maxSize]
                     next=foldr (uncurry M.insert) rest choices
                 in loop next (serial+length(expand g ctx tree)) (states+1) emitted results
