module Main where
import Json
import Syntax
import Grammar
import Evaluation
import Compression
import Agenda
import Search
import Control.Monad.State.Strict
import Control.Exception
import System.IO
import qualified Data.Map.Strict as M

handleRequest j
  | field "version" j /= Num 1 = Left "Unsupported protocol version"
  | otherwise = case str(field "operation" j) of
      "unify" -> do
        t<-runTI (unify (readType(field "left" j)) (readType(field "right" j)) >> resolve (readType(field "left" j)))
        pure (Obj [("type",typeJ(canonicalType t))])
      "infer" -> do
        t<-typeOf (signature g) env p
        pure (Obj [("type",typeJ t),("program",progJ p)])
      "beta" -> pure (Obj [("program",progJ(beta p))])
      "evaluate" -> do
        v<-evaluateJSON gridPrimitives p (arr(field "inputs" j))
        pure (Obj [("value",v)])
      "sample" -> do
        q<-sampleProgram g env req (map num(arr(field "uniforms" j)))
        lp<-logProbability g env req q
        pure (Obj [("program",progJ q),("log_probability",Num lp)])
      "versions" -> pure (Obj [("programs",Arr(map progJ(versions (integer(fallback(Num 1)(field "arity" j))) p)))])
      "compression_candidates" -> pure (Obj [("programs",Arr(map progJ(compressionCandidates g (map readFrontier(arr(field "frontiers" j))) (integer(fallback(Num 1)(field "arity" j))))))])
      "compress" -> do
        (g',fs,history)<-compress g (map readFrontier(arr(field "frontiers" j)))
          (integer(fallback(Num 1)(field "arity" j))) (integer(fallback(Num 5)(field "iterations" j)))
          (num(fallback(Num 1)(field "pseudo_counts" j))) (num(fallback(Num 1)(field "aic" j)))
          (num(fallback(Num 0.001)(field "structure_penalty" j)))
        pure(Obj[("grammar",grammarJ g'),("frontiers",Arr(map frontierInputJ fs)),("history",Arr history)])
      "score" -> do
        es<-summary g env req p
        pure (Obj [("log_probability",Num(score g es)),("events",Arr(map eventJ es))])
      "enumerate" ->
        let allPrograms=enumerate sg env req bound depth
        in pure (Obj [("programs",Arr [Obj [("program",progJ q),("type",typeJ req),("search_log_score",Num l),("log_prior",either (const Null) Num (logProbability g env req q))] | (l,q)<-take count allPrograms]), ("bounded_complete",Boolean(length allPrograms<=count)),("candidates_in_bound",Num(fromIntegral(length allPrograms)))])
      "enumerate_budget" ->
        let (ps,states,reason)=budgetEnumeration sg env req bound depth
              (integer(fallback(Num 1000)(field "max_size" j))) count (integer(fallback(Num 60000)(field "max_states" j)))
        in pure(Obj[("programs",Arr[Obj[("program",progJ q),("search_log_score",Num l),("log_prior",either (const Null) Num(logProbability g env req q)),("expanded_states_at_emission",Num(fromIntegral s))] | (l,q,s)<-ps]),("expanded_states",Num(fromIntegral states)),("stop_reason",Str reason)])
      "evaluate_batch" -> pure(Obj[("values",Arr[either (const Null) id(evaluateJSON gridPrimitives p (arr xs)) | xs<-arr(field "input_sets" j)])])
      "search_tasks" -> searchTasks g sg req (arr(field "tasks" j)) bound depth
        (integer(fallback(Num 7)(field "max_size" j))) count (integer(fallback(Num 60000)(field "max_states" j)))
        (integer(fallback(Num 3)(field "top_k" j)))
      "frontier" -> frontierJ <$> frontier g (readFrontier(field "frontier" j))
      "update" -> grammarJ <$> insideOutside g (map readFrontier(arr(field "frontiers" j))) (num(fallback (Num 1) (field "pseudo_counts" j))) (integer(fallback (Num 1) (field "iterations" j)))
      _ -> Left "Unknown operation"
  where g=readG(field "grammar" j)
        sg=readG(fallback (field "grammar" j) (field "search_grammar" j))
        env=map readType(arr(field "environment" j))
        p=readP(field "program" j)
        req=readType(field "request" j)
        count=integer(fallback (Num 100) (field "limit" j))
        depth=integer(fallback (Num 12) (field "maximum_depth" j))
        bound=num(fallback (Num 8) (field "upper_bound" j))
respond s = case parseJSON s >>= handleRequest of
  Left err -> Obj [("version",Num 1),("ok",Boolean False),("error",Str err)]
  Right r -> Obj [("version",Num 1),("ok",Boolean True),("result",r)]
main = do
  hSetBuffering stdout LineBuffering
  let loop = do
        eof<-isEOF
        if eof then pure () else do
          s<-getLine
          result<-try (evaluate (let out=render(respond s) in length out `seq` out)) :: IO (Either SomeException String)
          putStrLn (either (\e->render(Obj [("version",Num 1),("ok",Boolean False),("error",Str(show e))])) id result)
          loop
  loop
