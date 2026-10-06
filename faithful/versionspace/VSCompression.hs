{-# LANGUAGE FlexibleContexts #-}
{-# OPTIONS_GHC -Wno-x-partial #-}
-- Library learning over the shared version table: a port of the single-process
-- path of solvers/compression.ml (compression_step / compression_loop).
-- Probabilities, type inference and the invention utilities are the frozen
-- kernel's; nothing here enumerates explicit refactoring sets.
module VSCompression where

import Syntax
import Grammar
import Json
import Compression (closeFragment,freeVariables,nontrivial,leafSize,stripLambdas,frontierInputJ)
import VersionSpace
import qualified Data.IntMap.Strict as IM
import qualified Data.Map.Strict as M
import qualified Data.IntSet as IS
import Control.Monad
import Control.Monad.State.Strict
import Data.List (sort,sortOn)
import Data.Maybe (fromMaybe)

data Config = Config { arity :: Int, topK :: Int, topI :: Int, beamSize :: Int, inlining :: Bool
                     , pseudoCounts :: Double, aic :: Double, structurePenalty :: Double, tracing :: Bool
                     -- per-program sufficient statistics; Nothing is probability zero
                     , summarize :: Grammar -> Type -> P -> Maybe [Event] }

kernelSummary g r p = either (const Nothing) Just (summary g [] r p)

-- Utils.lse_list: a left fold that skips non-finite terms.
lseList :: [Double] -> Double
lseList = foldl lse2 (-1/0) where
  lse2 x y | invalid x = y
           | invalid y = x
           | x > y = x + log (1 + exp (y-x))
           | otherwise = y + log (1 + exp (x-y))

-- likelihood_summary: uses and normalisers are counted per distinct key, as in
-- the reference. Two programs with the same counts then get the same float
-- and tie exactly (stable sorts keep their input order); summing per event
-- instead would break such ties by rounding.
data Tally = Tally { tallyConstant :: !Double, tallyUses :: [(Int,Double)], tallyNormalisers :: [([Int],Double)] }
tally es = Tally (foldl (+) 0 (map constant es)) (count (map actual es)) (count (map (sort . possible) es))
  where count keys = M.toList (M.fromListWith (+) [(k,1) | k <- keys])
summaryLikelihood g (Tally c uses normalisers) =
  c + foldl (\a (k,n) -> a + n*(ws !! k)) 0 uses - foldl (\a (ks,n) -> a + n*lseList (map (ws !!) ks)) 0 normalisers
  where ws = variableWeight g:map weight (productions g)

-- grammar_induction_score: one inside-outside update of the weights (programs
-- weighted by their posterior under the incoming grammar), then the penalised
-- marginal likelihood of the frontiers under the refitted weights.
inductionScore cfg g fs
  | pseudoCounts cfg <= 0 = Left "pseudo_counts must be positive"
  | otherwise = Right (fitted, fold1 (+) marginals - aic cfg*fromIntegral (length (productions g)) - structurePenalty cfg*fromIntegral complexity)
  where
    summaries = [[(tally s,ll) | (p,ll) <- es, Just s <- [summarize cfg g r p]] | (r,es) <- fs]
    weighted = concat [[(exp (l-z),s) | (s,l) <- row] | ss <- summaries, let row = [(s,ll+summaryLikelihood g s) | (s,ll) <- ss], let z = lseList (map snd row)]
    -- mix_summaries
    mass select = M.fromListWith (\new old -> old+new) [(k,n*w) | (w,s) <- weighted, (k,n) <- select s]
    used = mass tallyUses
    normalised = M.toList (mass tallyNormalisers)
    act k = M.findWithDefault 0 k used
    poss k = foldl (+) 0 [m | (ks,m) <- normalised, k `elem` ks]
    ws = [log (act k+pseudoCounts cfg)-log (poss k+pseudoCounts cfg) | k <- [0..length (productions g)]]
    fitted = Grammar (head ws) (zipWith (\p w -> p { weight = w }) (productions g) (tail ws)) []
    marginals = [lseList [ll+summaryLikelihood fitted s | (s,ll) <- ss] | ss <- summaries]
    productionSize p = case term p of
      Inv e -> case snd (stripLambdas e) of
        App (App (Prim "fix1") _) b -> leafSize b
        body -> leafSize body
      _ -> 1
    complexity = sum (map productionSize (productions g)) :: Int

-- Raises (Left) exactly where the reference raises EtaExpandFailure or
-- UnificationFailure; the term is not beta-reduced first.
etaLong sig request expression = evalStateT (visit request [] expression) (initialContext [request]) where
  visit req env e = do
    r <- resolve req
    case (r,e) of
      (TC "->" [a,b],Lam body) -> Lam <$> visit b (a:env) body
      (_,Lam _) -> lift (Left "EtaExpandFailure")
      (TC "->" _,_) -> visit r env (Lam (App (shift 1 0 e) (Index 0)))
      _ -> do
        let (f,xs) = spine e
        ft <- case f of
          Index i | i < length env -> resolve (env !! i)
                  | otherwise -> lift (Left "Unbound index")
          Lam _ -> lift (Left "Not in beta long form")
          _ -> infer sig [] f
        unify r (returns ft)
        xt <- arguments <$> resolve ft
        if length xs /= length xt then lift (Left "EtaExpandFailure")
          else foldl App f <$> zipWithM (\x t -> visit t env x) xs xt

-- Replace literal occurrences of the invention source by the closed
-- invention applied to its free variables, then eta-expand.
rewriteWithInvention sig source = \request e -> do
  e' <- etaLong sig request (visit e)
  if beta e == beta e' then Right e' else Left "Rewrite changed the beta normal form"
  where
    mapping = freeVariables source
    applied = foldl App (closeFragment source) (map Index (reverse mapping))
    visit e | e == source = applied
            | otherwise = case e of
                App f x -> App (visit f) (visit x)
                Lam b -> Lam (visit b)
                _ -> e

-- Utils.occurs_multiple_times, in Hashtbl.to_alist order.
occursMultipleTimes :: [Int] -> [Int]
occursMultipleTimes xs = [k | (k,c) <- toAlist (IM.fromListWith (+) [(x,1::Int) | x <- xs]), c > 1]

-- The topK most probable programs of a frontier under the current grammar.
restrict cfg g (r,es) = (r, take (topK cfg) (map snd (sortOn fst
  [(negate (ll + maybe (-1/0) (summaryLikelihood g . tally) (summarize cfg g r p)), (p,ll)) | (p,ll) <- es])))

data Trial = Trial { trialScore :: Double, trialGrammar :: Grammar, trialFrontiers :: [Frontier], trialFallbacks :: Int }

versionSpaces cfg = mapM (\(_,es) -> mapM (\(p,_) -> incorporate p >>= nStepInversion (inlining cfg) (arity cfg)) es)

-- Candidates are the minimum-cost inhabitants of every space reachable from
-- at least two frontiers, kept when nontrivial and well typed once closed.
proposals cfg sig fs = do
  frontierIndices <- versionSpaces cfg fs
  forgetMemoisation
  t0 <- gets i2s
  inhabitants <- forM frontierIndices $ \indices -> do
    found <- mapM (fmap snd . minimumCostInhabitants True) (reachableVersions t0 indices)
    pure (IS.toAscList (IS.fromList (concat found)))
  t1 <- gets i2s
  let wellTyped p = either (const False) (const True) (typeOf sig [] (closeFragment p))
  pure (frontierIndices,[c | c <- occursMultipleTimes (concat inhabitants), let p = head (extract t1 c), wellTyped p, nontrivial p])

compressionStep cfg g original = do
  let fs = map (restrict cfg g) original
      sig = signature g
      propose = do
        (frontierIndices,candidates) <- proposals cfg sig fs
        ranked <- if null candidates then pure [] else beamCosts (beamSize cfg) candidates frontierIndices
        pure (frontierIndices,candidates,take (topI cfg) ranked)
      ((frontierIndices,candidates,ranked),table) = runState propose newVersionTable
      nodes = i2s table
      source i = head (extract nodes i)
      failed frontiers = Trial (-1/0) g frontiers 0
      -- try_invention_and_rewrite_frontiers
      attempt t indices frontiers i =
        let invention = closeFragment (source i)
        in case typeOf sig [] invention of
          Right tp | invention `notElem` map term (productions g) -> do
            let n = length (productions g) + 1
                uniform = Grammar (log 0.5) (map (\pr -> pr { weight = -log (fromIntegral n) }) (productions g ++ [Production invention tp 0])) []
                rewriter = rewriteWithInvention (signature uniform) (source i)
                extraction = forM (zip frontiers indices) $ \((r,es),js) -> forM (zip es js) $ \((p,ll),j) -> do
                  refactored <- fromMaybe p <$> minimalInhabitant t i True j
                  pure (r,p,ll,either (const p) id (rewriter r refactored))
                rewritten = evalState extraction (IM.empty,IM.empty)
                -- The reference scores an unparseable rewrite as probability zero;
                -- here the original program is kept so every output stays scorable.
                scorable (r,p,ll,q) = case summary uniform [] r q of Right _ -> ((q,ll),0); Left _ -> ((p,ll),1)
                checked = map (map scorable) rewritten
                frontiers' = [(r,map fst es) | ((r,_),es) <- zip frontiers checked]
            (fitted,s) <- inductionScore cfg uniform frontiers'
            pure (Trial s fitted frontiers' (sum (map snd (concat checked))))
          _ -> pure (failed frontiers)
  (_,initial) <- inductionScore cfg g fs
  let trials = [(c,i,either (const (failed fs)) id (attempt nodes frontierIndices fs i)) | (c,i) <- ranked]
      statistics = [("candidate_count",Num (fromIntegral (length candidates))),("evaluated",Num (fromIntegral (length ranked)))
                   ,("version_table_size",Num (fromIntegral (occupancy table)))
                   ,("reachable_versions",Num (fromIntegral (IS.size (reachableSet nodes (concat frontierIndices)))))
                   ,("log_version_sizes",Arr [Num (logVersionSize nodes j) | j <- concat frontierIndices])]
      trace = [("trace",Arr [Obj [("invented",progJ (closeFragment (source i))),("source",progJ (source i)),("discrete",Num c),("continuous",Num (trialScore t))
                                 ,("frontiers",Arr (map frontierInputJ (trialFrontiers t)))] | (c,i,t) <- trials]) | tracing cfg]
      rejected = pure (Nothing,Obj (("before",Num initial):statistics++trace))
  if null trials then rejected else do
    let (_,best,chosen) = minimumBy' (\(_,_,t) -> negate (trialScore t)) trials
    if trialScore chosen < initial then rejected else do
      -- Rewrite the entire frontiers, inverting the programs outside the topK.
      let (allIndices,table') = runState (versionSpaces cfg original) table
      final <- attempt (i2s table') allIndices original best
      pure (Just (trialGrammar final,trialFrontiers final),
            Obj ([("before",Num initial),("after",Num (trialScore chosen)),("invented",progJ (closeFragment (source best)))]
                 ++statistics++[("rewrite_fallbacks",Num (fromIntegral (trialFallbacks final)))]++trace))

-- compression_loop. Frontiers without programs take no part and are returned
-- unchanged. The history holds one entry per accepted invention; a rejected
-- final step is reported separately.
compressVS cfg g0 fs0 iterations = loop g0 { contexts = [] } solved iterations [] where
  solved = [f | f@(_,es) <- fs0, not (null es)]
  restore fs = go fs0 fs where
    go ((r,[]):rest) xs = (r,[]):go rest xs
    go (_:rest) (x:xs) = x:go rest xs
    go _ _ = []
  finish g fs history stopped = Right (g,restore fs,reverse history,stopped)
  loop g fs remaining history
    | remaining < 1 || null fs = finish g fs history Null
    | otherwise = do
        (result,report) <- compressionStep cfg g fs
        case result of
          Nothing -> finish g fs history report
          Just (g',fs') -> loop g' fs' (remaining-1) (report:history)

-- Diagnostics: the closed candidates of one step, and the explicit contents
-- of one program's n-step inversion space.
candidatesVS cfg g fs0 = [closeFragment (head (extract (i2s table) c)) | c <- candidates] where
  fs = map (restrict cfg g) [f | f@(_,es) <- fs0, not (null es)]
  ((_,candidates),table) = runState (proposals cfg (signature g) fs) newVersionTable

versionsVS il n p = (extract (i2s table) j, occupancy table, IS.size (reachableSet (i2s table) [j]), logVersionSize (i2s table) j)
  where (j,table) = runState (incorporate p >>= nStepInversion il n) newVersionTable
