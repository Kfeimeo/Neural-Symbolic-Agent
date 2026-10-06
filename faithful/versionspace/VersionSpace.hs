{-# OPTIONS_GHC -Wno-x-partial #-}
-- Shared version-space table: a port of solvers/versions.ml (pinned reference).
--
-- Every version space is hash-consed into one table, so n-step inverse-beta
-- refactorings of all frontier programs share structure instead of being
-- enumerated as explicit program sets. Function names follow the OCaml source.
--
-- Two kinds of incidental OCaml behaviour are reproduced because they decide
-- ties: (1) arguments are evaluated right to left, which fixes the order in
-- which new spaces receive identifiers; (2) Core's Hashtbl/Hash_set iteration
-- order (Base v0.11.1, the version linked into the reference binary).
-- Pure structural functions are additionally memoised; hash-consing makes
-- that unobservable (a repeated computation allocates nothing new).
module VersionSpace where

import Syntax
import qualified Data.Map.Strict as M
import qualified Data.IntMap.Strict as IM
import qualified Data.IntMap.Lazy as Lazy
import qualified Data.IntSet as IS
import Control.Monad
import Control.Monad.State.Strict
import Data.Bits
import Data.Word
import Data.List (sort,sortOn,foldl')
import Data.Maybe (catMaybes)

data VS = Union [Int] | ApplySpace !Int !Int | AbstractSpace !Int | IndexSpace !Int
        | TerminalSpace P | Universe | Void deriving (Eq,Ord,Show)

data Beam = Beam { defaultFunction, defaultArgument :: !Double
                 , relativeFunctionT, relativeArgumentT :: !(IM.IntMap Double) }

data VT = VT
  { occupancy :: !Int
  , i2s :: !(IM.IntMap VS)
  -- s2i, split by constructor
  , applyT :: !(IM.IntMap (IM.IntMap Int)), abstractT :: !(IM.IntMap Int), indexT :: !(IM.IntMap Int)
  , terminalT :: !(M.Map P Int), unionT :: !(M.Map [Int] Int)
  -- dynamic programming tables of the reference
  , recursiveInversionT :: !(IM.IntMap Int)
  , nStepT :: !(M.Map (Int,Int) Int)
  , substitutionT :: !(M.Map (Int,Int) (IM.IntMap Int))
  -- cost_table: minimum cost and all minimum-cost inhabitants, per position
  , argumentCostT, functionCostT :: !(IM.IntMap (Double,[Int]))
  , beamT :: !(IM.IntMap Beam)
  -- unobservable memoisation
  , shiftFreeT :: !(M.Map (Int,Int,Int) Int), betaPruningT :: !(M.Map (Int,Int) Int) }

type V = State VT

voidI, universeI :: Int
voidI = 0
universeI = 1

newVersionTable :: VT
newVersionTable = execState (incorporateSpace Void >> incorporateSpace Universe)
  (VT 0 IM.empty IM.empty IM.empty IM.empty M.empty M.empty IM.empty M.empty M.empty IM.empty IM.empty IM.empty M.empty M.empty)

indexTable :: Int -> V VS
indexTable j = gets ((IM.! j) . i2s)

incorporateSpace :: VS -> V Int
incorporateSpace v = do
  t <- get
  let found = case v of
        ApplySpace f x -> IM.lookup f (applyT t) >>= IM.lookup x
        AbstractSpace b -> IM.lookup b (abstractT t)
        IndexSpace i -> IM.lookup i (indexT t)
        TerminalSpace p -> M.lookup p (terminalT t)
        Union u -> M.lookup u (unionT t)
        Void -> if occupancy t > voidI then Just voidI else Nothing
        Universe -> if occupancy t > universeI then Just universeI else Nothing
  case found of
    Just i -> pure i
    Nothing -> do
      let i = occupancy t
          t' = t { occupancy = i+1, i2s = IM.insert i v (i2s t) }
      put $! case v of
        ApplySpace f x -> t' { applyT = IM.insertWith IM.union f (IM.singleton x i) (applyT t) }
        AbstractSpace b -> t' { abstractT = IM.insert b i (abstractT t) }
        IndexSpace k -> t' { indexT = IM.insert k i (indexT t) }
        TerminalSpace p -> t' { terminalT = M.insert p i (terminalT t) }
        Union u -> t' { unionT = M.insert u i (unionT t) }
        _ -> t'
      pure i

versionApply :: Int -> Int -> V Int
versionApply f x | f == voidI || x == voidI = pure voidI
                 | otherwise = incorporateSpace (ApplySpace f x)
versionAbstract :: Int -> V Int
versionAbstract b | b == voidI = pure voidI
                  | otherwise = incorporateSpace (AbstractSpace b)
versionIndex :: Int -> V Int
versionIndex = incorporateSpace . IndexSpace
versionTerminal :: P -> V Int
versionTerminal = incorporateSpace . TerminalSpace

union :: [Int] -> V Int
union vs
  | universeI `elem` vs = pure universeI
  | otherwise = do
      t <- gets i2s
      let flat v = case t IM.! v of Union stuff -> stuff; Void -> []; _ -> [v]
      case IS.toAscList (IS.fromList (concatMap flat vs)) of
        [] -> pure voidI
        [v] -> pure v
        u -> incorporateSpace (Union u)

incorporate :: P -> V Int
incorporate (Index i) = versionIndex i
incorporate (Lam b) = incorporate b >>= versionAbstract
incorporate (App f x) = do x' <- incorporate x; f' <- incorporate f; versionApply f' x'
incorporate e = versionTerminal e

extract :: IM.IntMap VS -> Int -> [P]
extract t j = case t IM.! j of
  Union u -> concatMap (extract t) u
  ApplySpace f x -> [App f' x' | f' <- extract t f, x' <- extract t x]
  IndexSpace i -> [Index i]
  Void -> []
  TerminalSpace p -> [p]
  AbstractSpace b -> map Lam (extract t b)
  Universe -> [Prim "UNIVERSE"]

-- Base v0.11.1 Hashtbl.Poly with int keys: buckets are indexed by
-- caml_hash land (length-1), each bucket is an AVL tree walked in key order,
-- and the bucket array (initially 128) doubles whenever length exceeds it.
camlHash :: Int -> Int
camlHash n = fromIntegral (final (mixed .&. 0xffffffff) .&. 0x3fffffff) where
  tagged = fromIntegral (2*n+1) :: Word64
  signed = fromIntegral tagged :: Int
  d0 = fromIntegral ((signed `shiftR` 32) `xor` (signed `shiftR` 63) `xor` signed) :: Word32
  d1 = d0 * 0xcc9e2d51
  d2 = (d1 `rotateL` 15) * 0x1b873593
  mixed = (d2 `rotateL` 13) * 5 + 0xe6546b64 :: Word32
  final h0 = let h1 = (h0 `xor` (h0 `shiftR` 16)) * 0x85ebca6b
                 h2 = (h1 `xor` (h1 `shiftR` 13)) * 0xc2b2ae35
             in h2 `xor` (h2 `shiftR` 16)

-- Hashtbl.iteri / fold order of a table holding exactly these distinct keys.
hashOrder :: [Int] -> [Int]
hashOrder ks = map snd (sort [(camlHash k .&. (len-1), k) | k <- ks]) where
  len = head [l | l <- iterate (*2) 128, length ks <= l]
iterateTable :: IM.IntMap a -> [(Int,a)]
iterateTable m = [(k, m IM.! k) | k <- hashOrder (IM.keys m)]
-- Hashtbl.to_alist, Hashtbl.keys and the Hash_set fold used by the reference
-- all cons onto an accumulator, i.e. reverse the iteration order.
toAlist :: IM.IntMap a -> [(Int,a)]
toAlist = reverse . iterateTable

shiftFree :: Int -> Int -> Int -> V Int
shiftFree c n index
  | n == 0 = pure index
  | otherwise = do
      cached <- gets (M.lookup (c,n,index) . shiftFreeT)
      case cached of
        Just r -> pure r
        Nothing -> do
          v <- indexTable index
          r <- case v of
            Union indices -> mapM (shiftFree c n) indices >>= union
            IndexSpace i | i < c -> pure index
                         | i >= n+c -> versionIndex (i-n)
                         | otherwise -> pure voidI
            ApplySpace f x -> do x' <- shiftFree c n x; f' <- shiftFree c n f; versionApply f' x'
            AbstractSpace b -> shiftFree (c+1) n b >>= versionAbstract
            _ -> pure index
          modify' (\t -> t { shiftFreeT = M.insert (c,n,index) r (shiftFreeT t) })
          pure r

shiftVersions :: Int -> Int -> Int -> V Int
shiftVersions c n index
  | n == 0 = pure index
  | otherwise = do
      v <- indexTable index
      case v of
        Union indices -> mapM (shiftVersions c n) indices >>= union
        IndexSpace i | i < c -> pure index
                     | i+n >= 0 -> versionIndex (i+n)
                     | otherwise -> pure voidI
        ApplySpace f x -> do x' <- shiftVersions c n x; f' <- shiftVersions c n f; versionApply f' x'
        AbstractSpace b -> shiftVersions (c+1) n b >>= versionAbstract
        _ -> pure index

intersection :: Int -> Int -> V Int
intersection a b = do
  va <- indexTable a
  vb <- indexTable b
  case (va,vb) of
    (Universe,_) -> pure b
    (_,Universe) -> pure a
    (Void,_) -> pure voidI
    (_,Void) -> pure voidI
    (Union xs,Union ys) -> sequence [intersection x y | x <- xs, y <- ys] >>= union
    (Union xs,_) -> mapM (\x -> intersection x b) xs >>= union
    (_,Union xs) -> mapM (\x -> intersection x a) xs >>= union
    (AbstractSpace b1,AbstractSpace b2) -> intersection b1 b2 >>= versionAbstract
    (ApplySpace f1 x1,ApplySpace f2 x2) -> do x <- intersection x1 x2; f <- intersection f1 f2; versionApply f x
    (IndexSpace i1,IndexSpace i2) | i1 == i2 -> pure a
    (TerminalSpace t1,TerminalSpace t2) | t1 == t2 -> pure a
    _ -> pure voidI

haveIntersection :: IM.IntMap VS -> Int -> Int -> Bool
haveIntersection t = go where
  go a0 b0
    | a0 == b0 = True
    | otherwise =
        let a = min a0 b0
            b = max a0 b0
        in case (t IM.! a, t IM.! b) of
          (Void,_) -> False
          (_,Void) -> False
          (Universe,_) -> True
          (_,Universe) -> True
          (Union xs,Union ys) -> any (\x -> any (go x) ys) xs
          (Union xs,_) -> any (\x -> go x b) xs
          (_,Union xs) -> any (\x -> go x a) xs
          (AbstractSpace b1,AbstractSpace b2) -> go b1 b2
          (ApplySpace f1 x1,ApplySpace f2 x2) -> go f1 f2 && go x1 x2
          (IndexSpace i1,IndexSpace i2) -> i1 == i2
          (TerminalSpace t1,TerminalSpace t2) -> t1 == t2
          _ -> False

-- Replaces (#(\ \ ... B) a1 a2 ... x y z) by B[a1,a2,...] x y z, top level only.
inline :: Int -> V Int
inline = il [] where
  il arguments j = do
    v <- indexTable j
    case v of
      ApplySpace f x -> il (x:arguments) f
      Union vs -> mapM (il arguments) vs >>= union
      TerminalSpace (Inv body) -> case makeSubstitution [] arguments body of
        Nothing -> pure voidI
        Just (used,body') -> do
          f <- applySubstitution 0 used body'
          foldM versionApply f (drop (length used) arguments)
      _ -> pure voidI
  makeSubstitution _ [] (Lam _) = Nothing
  makeSubstitution used [] body = Just (used,body)
  makeSubstitution used (x:xs) (Lam b) = makeSubstitution (x:used) xs b
  makeSubstitution used _ body = Just (used,body)
  applySubstitution k arguments expression = case expression of
    Index i | i < k -> versionIndex i
            | i-k < length arguments -> shiftVersions 0 k (arguments !! (i-k))
            | otherwise -> versionIndex (i - length arguments)
    App f x -> do x' <- applySubstitution k arguments x; f' <- applySubstitution k arguments f; versionApply f' x'
    Lam b -> applySubstitution (k+1) arguments b >>= versionAbstract
    _ -> incorporate expression

-- substitutions n j maps a value space v to the body space b such that
-- (\ b) v beta-reduces into j, for a redex created under n binders.
-- The universe key holds the bodies that do not mention the new variable.
substitutions :: Int -> Int -> V (IM.IntMap Int)
substitutions n index = do
  cached <- gets (M.lookup (index,n) . substitutionT)
  case cached of
    Just m -> pure m
    Nothing -> do
      s <- shiftFree 0 n index
      m0 <- if s /= voidI then IM.singleton s <$> versionIndex n else pure IM.empty
      let add k d = IM.insertWith (\_ old -> old) k d
          merge table = foldM (\acc (k,ds) -> do d <- union ds; pure (IM.insert k d acc)) m0 (iterateTable table)
          collect acc (k,d) = IM.insertWith (++) k [d] acc
      v <- indexTable index
      m <- case v of
        TerminalSpace _ -> pure (add universeI index m0)
        IndexSpace i -> do
          b <- if i < n then pure index else versionIndex (1+i)
          pure (add universeI b m0)
        AbstractSpace b -> do
          child <- substitutions (n+1) b
          foldM (\acc (k,d) -> do d' <- versionAbstract d; pure (add k d' acc)) m0 (iterateTable child)
        Union u -> do
          tables <- mapM (substitutions n) u
          merge (foldl' (\acc table -> foldl' collect acc (iterateTable table)) IM.empty tables)
        ApplySpace f x -> do
          fm <- substitutions n f
          xm <- substitutions n x
          let pair acc ((v1,f'),(v2,x')) = do
                t <- gets i2s
                if haveIntersection t v1 v2
                  then do
                    vi <- intersection v1 v2
                    a <- versionApply f' x'
                    pure (collect acc (vi,a))
                  else pure acc
          foldM pair IM.empty [(l,r) | l <- iterateTable fm, r <- iterateTable xm] >>= merge
        _ -> pure m0
      modify' (\t -> t { substitutionT = M.insert (index,n) m (substitutionT t) })
      pure m

recursiveInversion :: Int -> V Int
recursiveInversion j = do
  cached <- gets (IM.lookup j . recursiveInversionT)
  case cached of
    Just ri -> pure ri
    Nothing -> do
      v <- indexTable j
      ri <- case v of
        Union u -> mapM recursiveInversion u >>= union
        _ -> do
          table <- substitutions 0 j
          top <- fmap catMaybes $ forM (toAlist table) $ \(value,body) -> do
            b <- indexTable body
            if value == universeI || b == IndexSpace 0 then pure Nothing
              else Just <$> (versionAbstract body >>= \l -> versionApply l value)
          child <- case v of
            ApplySpace f x -> do
              rx <- recursiveInversion x
              second <- versionApply f rx
              rf <- recursiveInversion f
              first <- versionApply rf x
              pure [first,second]
            AbstractSpace b -> do r <- recursiveInversion b >>= versionAbstract; pure [r]
            _ -> pure []
          union (child ++ top)
      modify' (\t -> t { recursiveInversionT = IM.insert j ri (recursiveInversionT t) })
      pure ri

-- Removes refactorings whose beta-reduction is not a single top-down pass.
betaPruning :: Int -> V Int
betaPruning = go False True where
  go isApplied canBeta j = do
    let key = (fromEnum isApplied*2 + fromEnum canBeta, j)
    cached <- gets (M.lookup key . betaPruningT)
    case cached of
      Just r -> pure r
      Nothing -> do
        v <- indexTable j
        r <- case v of
          ApplySpace f x -> do f' <- go True canBeta f; x' <- go False canBeta x; versionApply f' x'
          AbstractSpace b | isApplied && not canBeta -> pure voidI
                          | isApplied -> go False False b >>= versionAbstract
                          | otherwise -> go False canBeta b >>= versionAbstract
          Union u -> mapM (go isApplied canBeta) u >>= union
          _ -> pure j
        modify' (\t -> t { betaPruningT = M.insert key r (betaPruningT t) })
        pure r

nStepInversion :: Bool -> Int -> Int -> V Int
nStepInversion il n j = do
  cached <- gets (M.lookup (n,j) . nStepT)
  case cached of
    Just ns -> pure ns
    Nothing -> do
      ns <- visit j >>= betaPruning
      modify' (\t -> t { nStepT = M.insert (n,j) ns (nStepT t) })
      pure ns
  where
    step v | il = do i <- inline v; r <- recursiveInversion v; union [r,i]
           | otherwise = recursiveInversion v
    nStep completed current = do
      rest <- if completed == n then pure [] else step current >>= nStep (completed+1)
      pruned <- betaPruning current
      pure (pruned:rest)
    visit k = do
      v <- indexTable k
      children <- case v of
        ApplySpace f x -> do x' <- visit x; f' <- visit f; versionApply f' x'
        AbstractSpace b -> visit b >>= versionAbstract
        IndexSpace _ -> pure k
        TerminalSpace _ -> pure k
        _ -> error "n_step_inversion: not a program"
      steps <- nStep 0 k
      union (children:steps)

-- Drops only the memoisation that the reference does not have.
forgetMemoisation :: V ()
forgetMemoisation = modify' (\t -> t { shiftFreeT = M.empty, betaPruningT = M.empty })

reachableSet :: IM.IntMap VS -> [Int] -> IS.IntSet
reachableSet t = foldl' visit IS.empty where
  visit seen j
    | IS.member j seen = seen
    | otherwise = let seen' = IS.insert j seen in case t IM.! j of
        AbstractSpace b -> visit seen' b
        ApplySpace f x -> visit (visit seen' f) x
        Union u -> foldl' visit seen' u
        _ -> seen'
reachableVersions :: IM.IntMap VS -> [Int] -> [Int]
reachableVersions t = reverse . hashOrder . IS.toList . reachableSet t

logVersionSize :: IM.IntMap VS -> Int -> Double
logVersionSize t root = memo IM.! root where
  memo = Lazy.fromSet size (reachableSet t [root])
  size j = case t IM.! j of
    ApplySpace f x -> memo IM.! f + memo IM.! x
    AbstractSpace b -> memo IM.! b
    Union u -> let xs = map (memo IM.!) u; m = maximum xs in m + log (sum (map (exp . subtract m) xs))
    _ -> 0

epsilonCost :: Double
epsilonCost = 0.01
invalid :: Double -> Bool
invalid x = isNaN x || isInfinite x
fold1 :: (a -> a -> a) -> [a] -> a
fold1 f l = foldr f (head l) (tail l)
-- Utils.minimum_by keeps the LAST minimal element.
minimumBy' :: Ord b => (a -> b) -> [a] -> a
minimumBy' f = foldl1 (\x y -> if f x < f y then x else y)

-- Minimum cost of each space together with every inhabitant achieving it.
-- Leaves cost 1, applications and abstractions epsilon; an abstraction may
-- not stand in function position.
minimumCostInhabitants :: Bool -> Int -> V (Double,[Int])
minimumCostInhabitants canBeLambda j = do
  cached <- gets (IM.lookup j . table)
  case cached of
    Just c -> pure c
    Nothing -> do
      v <- indexTable j
      (cost,indices) <- case v of
        IndexSpace _ -> pure (1,[j])
        TerminalSpace _ -> pure (1,[j])
        Union u -> do
          children <- mapM (minimumCostInhabitants canBeLambda) u
          let c = fold1 min (map fst children)
          pure (if invalid c then (c,[]) else (c, concat [p | (cost',p) <- children, cost' == c]))
        AbstractSpace b
          | canBeLambda -> do
              (cost',children) <- minimumCostInhabitants True b
              inhabitants <- mapM versionAbstract children
              pure (cost'+epsilonCost, inhabitants)
          | otherwise -> pure (1/0,[])
        ApplySpace f x -> do
          (fc,fs) <- minimumCostInhabitants False f
          (xc,xs) <- minimumCostInhabitants True x
          if invalid fc || invalid xc then pure (1/0,[]) else do
            inhabitants <- sequence [versionApply f' x' | f' <- fs, x' <- xs]
            pure (fc+xc+epsilonCost, inhabitants)
        _ -> error "minimum_cost_inhabitants: void or universe"
      let c = (cost, IS.toAscList (IS.fromList indices))
      modify' (\t -> if canBeLambda then t { argumentCostT = IM.insert j c (argumentCostT t) }
                                    else t { functionCostT = IM.insert j c (functionCostT t) })
      pure c
  where table = if canBeLambda then argumentCostT else functionCostT

-- Cheap cost table for one given invention; never allocates, hence pure.
type Cheap = State (IM.IntMap Double,IM.IntMap Double)

minimalInhabitantCost :: IM.IntMap VS -> Int -> Bool -> Int -> Cheap Double
minimalInhabitantCost t invention = go where
  go canBeLambda j = do
    cached <- gets (IM.lookup j . (if canBeLambda then fst else snd))
    case cached of
      Just c -> pure c
      Nothing -> do
        c <- if haveIntersection t invention j then pure 1 else case t IM.! j of
          IndexSpace _ -> pure 1
          TerminalSpace _ -> pure 1
          Union u -> fold1 min <$> mapM (go canBeLambda) u
          AbstractSpace b | canBeLambda -> (epsilonCost +) <$> go True b
                          | otherwise -> pure (1/0)
          ApplySpace f x -> do fc <- go False f; xc <- go True x; pure (epsilonCost + fc + xc)
          _ -> error "minimal_inhabitant_cost: void or universe"
        modify' (\(a,f) -> if canBeLambda then (IM.insert j c a,f) else (a,IM.insert j c f))
        pure c

minimalInhabitant :: IM.IntMap VS -> Int -> Bool -> Int -> Cheap (Maybe P)
minimalInhabitant t invention = go where
  cost = minimalInhabitantCost t invention
  single j = case extract t j of [p] -> p; _ -> error "minimal_inhabitant: not a singleton"
  go canBeLambda j = do
    c <- cost canBeLambda j
    if invalid c then pure Nothing
      else if c == 1 && haveIntersection t invention j then pure (Just (single invention))
      else case t IM.! j of
        Union u -> do
          costs <- mapM (cost canBeLambda) u
          go canBeLambda (fst (minimumBy' snd (zip u costs)))
        AbstractSpace b -> fmap Lam <$> go True b
        ApplySpace f x -> do f' <- go False f; x' <- go True x; pure (App <$> f' <*> x')
        _ -> pure (Just (single j))

freeVariableCount :: P -> Int
freeVariableCount = IS.size . IS.fromList . go 0 where
  go d (Index i) = [i-d | i >= d]
  go d (Lam b) = go (d+1) b
  go d (App f x) = go d f ++ go d x
  go _ _ = []

relativeFunction, relativeArgument :: Beam -> Int -> Double
relativeFunction b i = IM.findWithDefault (defaultFunction b) i (relativeFunctionT b)
relativeArgument b i = IM.findWithDefault (defaultArgument b) i (relativeArgumentT b)

-- For every space, the cost of its cheapest inhabitant when one candidate is
-- available at cost 1 + (number of its free variables), for the best
-- beam-size candidates. A single bottom-up pass scores all candidates.
beamCostTable :: Int -> [Int] -> [[Int]] -> V ()
beamCostTable bs candidates frontierIndices = do
  modify' (\t -> t { beamT = IM.empty })
  t <- gets i2s
  let candidateCost = IM.fromList [(k, 1 + fromIntegral (freeVariableCount p)) | k <- candidates, let [p] = extract t k]
      narrow m | IM.size m > bs = IM.fromList (take bs (sortOn snd (toAlist m)))
               | otherwise = m
      relax = IM.unionWith min
      calculate j = do
        cached <- gets (IM.lookup j . beamT)
        case cached of
          Just bm -> pure bm
          Nothing -> do
            (da,inhabitants) <- minimumCostInhabitants True j
            (df,_) <- minimumCostInhabitants False j
            let own = IM.fromList [(c,cost) | c <- inhabitants, Just cost <- [IM.lookup c candidateCost]]
            v <- indexTable j
            (rf,ra) <- case v of
              AbstractSpace b -> do
                child <- calculate b
                pure (own, relax own (IM.map (+epsilonCost) (relativeArgumentT child)))
              ApplySpace f x -> do
                fb <- calculate f
                xb <- calculate x
                let domain = IM.keys (relativeFunctionT fb) ++ IM.keys (relativeArgumentT xb)
                    r = relax own (IM.fromList [(i, epsilonCost + relativeFunction fb i + relativeArgument xb i) | i <- domain])
                pure (r,r)
              Union u -> do
                children <- mapM calculate u
                pure (foldl' relax own (map relativeFunctionT children), foldl' relax own (map relativeArgumentT children))
              _ -> pure (own,own)
            let bm = Beam df da (narrow rf) (narrow ra)
            modify' (\s -> s { beamT = IM.insert j bm (beamT s) })
            pure bm
  mapM_ (mapM_ calculate) frontierIndices

-- Corpus size (sum over frontiers of the cheapest program) per candidate.
beamCosts' :: Int -> [Int] -> [[Int]] -> V [Double]
beamCosts' bs candidates frontierIndices = do
  beamCostTable bs candidates frontierIndices
  beams <- gets beamT
  modify' (\t -> t { beamT = IM.empty })
  let frontierBeams = map (map (beams IM.!)) frontierIndices
      score i = fold1 (+) [fold1 min [min (relativeArgument b i) (relativeFunction b i) | b <- bms] | bms <- frontierBeams]
  pure (map score candidates)

beamCosts :: Int -> [Int] -> [[Int]] -> V [(Double,Int)]
beamCosts bs candidates frontierIndices = do
  scores <- beamCosts' bs candidates frontierIndices
  pure (sortOn fst (zip scores candidates))
