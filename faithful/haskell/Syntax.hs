{-# LANGUAGE FlexibleContexts #-}
module Syntax where

import qualified Data.Map.Strict as M
import Data.List (nub)
import Control.Monad.State.Strict
import Control.Monad (zipWithM_)
import Json

data Type = TV Int | TC String [Type] deriving (Eq,Ord)
instance Show Type where
  show (TV i) = "t"++show i
  show (TC "->" [a,b]) = "("++show a++" -> "++show b++")"
  show (TC n []) = n
  show (TC n ts) = n++show ts
arrow a b = TC "->" [a,b]
data P = Prim String | Index Int | App P P | Lam P | Inv P deriving (Eq,Ord)
instance Show P where
  show (Prim n) = n
  show (Index i) = "$"++show i
  show (App f x) = "("++show f++" "++show x++")"
  show (Lam b) = "(lambda "++show b++")"
  show (Inv b) = "#"++show b
type Sub = M.Map Int Type
type TI = StateT (Int,Sub) (Either String)
runTI :: TI a -> Either String a
runTI t = evalStateT t (1000,M.empty)
fresh = do (n,s)<-get; put (n+1,s); pure (TV n)
apply s (TV i) = maybe (TV i) (apply s) (M.lookup i s)
apply s (TC n ts) = TC n (map (apply s) ts)
resolve t = gets (\(_,s)->apply s t)
vars (TV i) = [i]
vars (TC _ ts) = nub (concatMap vars ts)
unify a b = do
  a'<-resolve a; b'<-resolve b
  case (a',b') of
    _ | a'==b' -> pure ()
    (TV i,t) -> bind i t
    (t,TV i) -> bind i t
    (TC n xs,TC m ys) | n==m && length xs==length ys -> zipWithM_ unify xs ys
    _ -> lift (Left ("Cannot unify "++show a'++" and "++show b'))
  where bind i t | i `elem` vars t = lift (Left "Occurs check")
                 | otherwise = modify (\(n,s)->(n,M.insert i t s))
instantiate t = do
  vs<-mapM (const fresh) (vars t)
  pure (apply (M.fromList (zip (vars t) vs)) t)
infer sig env (Prim n) = maybe (lift (Left ("Unknown primitive "++n))) instantiate (lookup n sig)
infer _ env (Index i) | i>=0 && i<length env = resolve (env!!i)
infer _ _ (Index _) = lift (Left "Unbound index")
infer sig env (Lam b) = do a<-fresh; t<-infer sig (a:env) b; resolve (arrow a t)
infer sig env (App f x) = do tf<-infer sig env f; tx<-infer sig env x; r<-fresh; unify tf (arrow tx r); resolve r
infer sig _ (Inv b) = do t<-infer sig [] b; resolve t >>= instantiate
canonicalType t = rename t where
  mapping=M.fromList(zip(vars t)[0..])
  rename (TV i)=TV(mapping M.! i)
  rename (TC n ts)=TC n(map rename ts)
initialContext ts = (maximum (1000:[i+1 | t<-ts,i<-vars t]),M.empty)
typeOf sig env p = canonicalType <$> evalStateT (infer sig env p >>= resolve) (initialContext env)
returns (TC "->" [_,r]) = returns r
returns t = t
arguments (TC "->" [a,r]) = a:arguments r
arguments _ = []
spine (App f x) = let (h,xs)=spine f in (h,xs++[x])
spine p = (p,[])
shift d cutoff (Index i) = Index (if i>=cutoff then i+d else i)
shift d c (App f x) = App (shift d c f) (shift d c x)
shift d c (Lam b) = Lam (shift d (c+1) b)
shift _ _ p = p
subst j x (Index i) | i==j = x
subst j x (App f a) = App (subst j x f) (subst j x a)
subst j x (Lam b) = Lam (subst (j+1) (shift 1 0 x) b)
subst _ _ p = p
beta (App f x) = case beta f of
  Lam b -> beta (shift (-1) 0 (subst 0 (shift 1 0 x) b))
  f' -> App f' (beta x)
beta (Lam b) = Lam (beta b)
beta (Inv b) = beta b
beta p = p
size (App f x) = 1+size f+size x
size (Lam b) = 1+size b
size _ = 1
typeJ (TV i) = Obj [("var",Num (fromIntegral i))]
typeJ (TC n ts) = Obj [("constructor",Str n),("arguments",Arr (map typeJ ts))]
readType j = case field "var" j of
  Num n -> TV (round n)
  _ -> TC (str (field "constructor" j)) (map readType (arr (field "arguments" j)))
progJ (Prim n) = Obj [("primitive",Str n)]
progJ (Index i) = Obj [("index",Num (fromIntegral i))]
progJ (App f x) = Obj [("application",Arr [progJ f,progJ x])]
progJ (Lam b) = Obj [("abstraction",progJ b)]
progJ (Inv b) = Obj [("invented",progJ b)]
readP j | field "primitive" j /= Null = Prim (str (field "primitive" j))
        | field "index" j /= Null = Index (integer (field "index" j))
        | field "application" j /= Null = case arr (field "application" j) of [f,x]->App (readP f) (readP x); _->error "Application arity"
        | field "abstraction" j /= Null = Lam (readP (field "abstraction" j))
        | field "invented" j /= Null = Inv (readP (field "invented" j))
        | otherwise = error "Unknown AST"
