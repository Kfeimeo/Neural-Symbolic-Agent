module Evaluation where
import Syntax
import Json
import Data.List (transpose)
import qualified Data.Set as S

-- Domain values are separated from the language and probabilistic kernel.
data Value = Data J | Function (Value -> Either String Value)
applyValue (Function f) x = f x
applyValue _ _ = Left "Applying a non-function"
evaluateP primitives env (Prim n) = maybe (Left ("No evaluator for "++n)) Right (lookup n primitives)
evaluateP _ env (Index i) | i>=0 && i<length env = Right (env!!i)
evaluateP _ _ (Index _) = Left "Unbound variable"
evaluateP primitives env (Lam b) = Right (Function (\x->evaluateP primitives (x:env) b))
evaluateP primitives env (App f x) = do vf<-evaluateP primitives env f; vx<-evaluateP primitives env x; applyValue vf vx
evaluateP primitives _ (Inv b) = evaluateP primitives [] b
evaluateJSON ps p xs = do
  f<-evaluateP ps [] p
  v<-foldl (\a x->a >>= (\f->applyValue f (Data x))) (Right f) xs
  case v of Data j -> Right j; _ -> Left "Result is a function"
unaryGrid f = Function (\v->case v of
  Data (Arr rows) -> Right (Data (Arr (map Arr (f (map arr rows)))))
  _ -> Left "Expected grid")
numeric f = Function (\v->case v of Data (Num x)->Right(Data(Num(f x))); _->Left "Expected number")
gridPrimitives =
  [("rotate90",unaryGrid (map reverse . transpose)),("flipH",unaryGrid (map reverse)),
   ("flipV",unaryGrid reverse),("transpose",unaryGrid transpose),
   ("invert",unaryGrid (map(map (\x->Num (if num x==0 then 0 else 4-num x))))),
   ("identity",Function Right),("zero",Data (Num 0)),("succ",numeric (+1)),
   ("truth",Data(Boolean True)),
   ("choose",Function (\v->Right(Function(\a->Right(Function(\b->case v of Data(Boolean c)->Right(if c then a else b);_->Left "Expected bool"))))))] ++ toyPrimitives

-- Object wire representation: sorted [row,column,color] cells. Components
-- connect all nonzero colors with four-neighbour adjacency, matching the toy DSL.
jsonFunction 0 f xs = either (error . ("Domain: "++)) Data (f(reverse xs))
jsonFunction n f xs = Function (\v->case v of Data x->Right(jsonFunction (n-1) f (x:xs));_->Left "Expected concrete domain value")
liftJSON n f = jsonFunction n (Right . f) []
gridRows = map arr . arr
gridJSON = Arr . map Arr
cellJ (r,c,v)=Arr[Num(fromIntegral r),Num(fromIntegral c),v]
cell j=case arr j of [r,c,v]->(integer r,integer c,v);_->error "Object cell arity"
components j = loop occupied where
  rows=gridRows j
  occupied=S.fromList [(r,c) | (r,row)<-zip [0..] rows,(c,v)<-zip [0..] row,num v/=0]
  flood pending remaining found = case pending of
    [] -> (remaining,found)
    (r,c):rest -> let ns=[q | q<-[(r-1,c),(r+1,c),(r,c-1),(r,c+1)],S.member q remaining]
                 in flood (ns++rest) (foldr S.delete remaining ns) ((r,c):found)
  loop remaining | S.null remaining=[]
                 | otherwise=let first=S.findMin remaining
                                 (rest,found)=flood [first] (S.delete first remaining) []
                             in Arr[cellJ(r,c,rows!!r!!c) | (r,c)<-S.toAscList(S.fromList found)]:loop rest
cropObject j = case map cell(arr j) of
  [] -> gridJSON [[Num 0]]
  cells -> let r0=minimum[r | (r,_,_)<-cells]; r1=maximum[r | (r,_,_)<-cells]
               c0=minimum[c | (_,c,_)<-cells]; c1=maximum[c | (_,c,_)<-cells]
           in gridJSON[[maybe (Num 0) id (lookup (r,c) [((a,b),v) | (a,b,v)<-cells]) | c<-[c0..c1]] | r<-[r0..r1]]
largestObject xs = foldl (\best x->if length(arr x)>length(arr best) then x else best) (Arr []) xs
toyPrimitives =
  [("rotate180",unaryGrid (reverse . map reverse)),
   ("trim",liftJSON 1 (\[g]->cropObject(Arr[cellJ(r,c,v) | (r,row)<-zip[0..](gridRows g),(c,v)<-zip[0..]row,num v/=0]))),
   ("recolor",liftJSON 3 (\[g,a,b]->gridJSON(map(map(\v->if v==a then b else v))(gridRows g)))),
   ("objects",liftJSON 1 (\[g]->Arr(components g))),
   ("largest",liftJSON 1 (\[os]->largestObject(arr os))),
   ("crop",liftJSON 1 (\[o]->cropObject o)),
   ("translate",liftJSON 3 (\[g,dr,dc]->let rows=gridRows g;h=length rows;w=length(head rows);a=integer dr;b=integer dc
      in gridJSON[[if r-a>=0 && r-a<h && c-b>=0 && c-b<w then rows!!(r-a)!!(c-b) else Num 0 | c<-[0..w-1]] | r<-[0..h-1]])),
   ("count",liftJSON 1 (\[os]->Num(fromIntegral(length(arr os))))),
   ("is_empty",liftJSON 1 (\[os]->Boolean(null(arr os)))),
   ("if_grid",liftJSON 3 (\[b,a,c]->if b==Boolean True then a else c)),
   ("border",unaryGrid (\rows->let edge=replicate(length(head rows)+2)(Num 0) in edge:map(\r->Num 0:r++[Num 0])rows++[edge])),
   ("solid",liftJSON 2 (\[g,c]->gridJSON(map(map(\v->if num v==0 then Num 0 else c))(gridRows g))))] ++
   [(name,Data(Num value)) | (name,value)<-[("red",1),("blue",2),("green",3),("one",1),("minus_one",-1)]]
