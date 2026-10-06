-- Likelihood summaries exactly as the reference OCaml compressor computes them
-- (solvers/grammar.ml make_likelihood_summary with FastType.compile_unifier).
--
-- They differ from the frozen kernel, which follows the Python reference, only
-- for polymorphic libraries: the OCaml request type is passed down without
-- applying the typing context, and the compiled unifier binds a request
-- variable to a production's return type without consulting its existing
-- binding. A request that is an already-bound type variable therefore admits
-- every production as a competitor, which enlarges the normaliser. For
-- monomorphic libraries the two definitions coincide.
module ReferenceLikelihood where

import Syntax
import Grammar
import qualified Data.IntMap.Strict as IM
import Control.Monad
import Control.Monad.State.Strict

type Context = (Int,IM.IntMap Type)

polymorphic (TV _) = True
polymorphic (TC _ ts) = any polymorphic ts
applyContext k@(_,bindings) t = case t of
  _ | not (polymorphic t) -> t
  TC c xs -> TC c (map (applyContext k) xs)
  TV j -> maybe t (applyContext k) (IM.lookup j bindings)
bindTID j t (next,bindings) = (next,IM.insert j t bindings)
makeTIDs n (next,bindings) = (map TV [next..next+n-1],(next+n,bindings))
occurs i (TV j) = i == j
occurs i (TC _ ts) = any (occurs i) ts

unifyContext :: Context -> Type -> Type -> Maybe Context
unifyContext k a b
  | not (polymorphic t1) && not (polymorphic t2) = if t1 == t2 then Just k else Nothing
  | otherwise = case (t1,t2) of
      (TV j,t) -> variable j t
      (t,TV j) -> variable j t
      (TC k1 as1,TC k2 as2) | k1 == k2 && length as1 == length as2 -> foldM (\k' (x,y) -> unifyContext k' x y) k (zip as1 as2)
      _ -> Nothing
  where t1 = applyContext k a
        t2 = applyContext k b
        variable j t | t1 == t2 = Just k
                     | occurs j t = Nothing
                     | otherwise = Just (bindTID j t k)

mightUnify (TC k1 as1) (TC k2 as2) = k1 == k2 && length as1 == length as2 && and (zipWith mightUnify as1 as2)
mightUnify (TV _) _ = True
mightUnify _ (TV _) = True

-- compile_unifier: unify a production's return type with the request and
-- yield its argument types. The store maps the production's own (canonical)
-- type variables to the request fragments they were matched against.
fastUnify :: Type -> Context -> Type -> Maybe (Context,[Type])
fastUnify t context request = do
  (k,store) <- fu (returns t) request (context,IM.empty)
  let (as,(next,_)) = runState (mapM makeSlow (arguments t)) (fst k,store)
  pure ((next,snd k),as)
  where
    fu (TV r) s (k,store) = case IM.lookup r store of
      Nothing -> Just (k,IM.insert r s store)
      Just s' -> (\k' -> (k',store)) <$> unifyContext k s s'
    fu (TC n fs) (TC n' ss) matched
      | n == n' && length fs == length ss = foldM (\st (f,s) -> fu f s st) matched (zip fs ss)
      | otherwise = Nothing
    fu f@(TC n fs) (TV j) (k,store)
      | not (polymorphic f) = Just (bindTID j f k,store)
      | otherwise = let (new,k') = makeTIDs (length fs) k
                    in foldM (\st (f',s) -> fu f' s st) (bindTID j (TC n new) k',store) (zip fs new)
    makeSlow (TC n xs) = TC n <$> mapM makeSlow xs
    makeSlow (TV r) = do
      (next,store) <- get
      case IM.lookup r store of
        Just s -> pure s
        Nothing -> do put (next+1,IM.insert r (TV next) store); pure (TV next)

-- unifying_expressions: (variable candidates, production candidates).
unifyingExpressions g environment request k = (variables,library) where
  variables = [(i,arguments (applyContext k' t'),k') | (i,t) <- zip [0..] environment, let t' = applyContext k t
              , mightUnify (returns t') request, Just k' <- [unifyContext k (returns t') request]]
  library = [(i,as,k') | (i,pr) <- zip [1..] (productions g), mightUnify (returns (scheme pr)) request
            , Just (k',as) <- [fastUnify (canonicalType (scheme pr)) k request]]

-- Nothing is the reference's likelihood of negative infinity.
referenceSummary :: Grammar -> Type -> P -> Maybe [Event]
referenceSummary g request program = evalStateT (summarize request [] program) (0,IM.empty) where
  summarize (TC "->" [argument,result]) environment (Lam body) = summarize result (argument:environment) body
  summarize (TC "->" _) _ _ = lift Nothing
  summarize r environment p = do
    k <- get
    let (variables,library) = unifyingExpressions g environment r k
        (f,xs) = spine p
        chosen = case f of
          Index j -> [(0,as,k') | (i,as,k') <- variables, i == j]
          _ -> [c | c@(i,_,_) <- library, term (productions g !! (i-1)) == f]
    case chosen of
      (i,as,k'):_ | length as == length xs -> do
        put k'
        let event = Event "" i ([0 | not (null variables)]++[j | (j,_,_) <- library])
                      (if i == 0 then -log (fromIntegral (length variables)) else 0)
        (event:) . concat <$> zipWithM (\x t -> summarize t environment x) xs as
      _ -> lift Nothing
