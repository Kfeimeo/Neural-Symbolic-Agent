-- Protocol boundary for the shared version-space compressor. Every other
-- operation is served by the frozen kernel through the compression bridge.
module VSMain where
import qualified Bridge
import Syntax
import Json
import Grammar
import Compression (frontierInputJ)
import VSCompression
import ReferenceLikelihood (referenceSummary)

handle j = case field "operation" j of
  Str "vs_compress" -> versioned $ do
    (g',fs,history,stopped) <- compressVS config g frontiers (int 5 "iterations")
    pure (Obj [("grammar",grammarJ g'),("frontiers",Arr (map frontierInputJ fs)),("history",Arr history),("final_step",stopped)])
  Str "vs_candidates" -> versioned (pure (Obj [("programs",Arr (map progJ (candidatesVS config g frontiers)))]))
  Str "vs_versions" -> versioned $
    let (ps,table,reachable,logSize) = versionsVS (inlining config) (arity config) (readP (field "program" j))
        programs = [("programs",Arr (map progJ ps)) | field "count_only" j /= Boolean True]
    in pure (Obj (programs++[("version_table_size",Num (fromIntegral table)),("reachable_versions",Num (fromIntegral reachable)),("log_version_size",Num logSize)]))
  _ -> Bridge.handle j
  where
    versioned r = if field "version" j /= Num 1 then Left "Unsupported protocol version" else r
    g = readG (field "grammar" j)
    frontiers = map readFrontier (arr (field "frontiers" j))
    int d k = integer (fallback (Num d) (field k j))
    real d k = num (fallback (Num d) (field k j))
    config = Config { arity = int 1 "arity", topK = case field "top_k" j of Num n -> round n; _ -> maxBound
                    , topI = int 300 "top_i", beamSize = int 1000000 "beam_size", inlining = field "inline" j /= Boolean False
                    , pseudoCounts = real 1 "pseudo_counts", aic = real 1 "aic", structurePenalty = real 0.001 "structure_penalty"
                    , tracing = field "trace" j == Boolean True
                    , summarize = if field "likelihood" j == Str "ocaml" then referenceSummary else kernelSummary }

main = Bridge.serve handle
