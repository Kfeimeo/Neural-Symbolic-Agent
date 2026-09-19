-- Additional protocol boundary; imports the frozen implementation unchanged.
module Bridge where
import qualified Main as Core
import Syntax
import Json
import Grammar
import Compression
import Evaluation
import System.IO
import Control.Exception (try,evaluate,SomeException)

handle j = case str(field "operation" j) of
  "compression_objective" -> do
    (fitted,s)<-objective g fs 1 1 0.001
    pure(Obj[("grammar",grammarJ fitted),("objective",Num s)])
  "compression_trial" -> do
    tp<-typeOf(signature g)[]inv
    let uniform=Grammar 0 (map (\pr->pr{weight=0})(productions g)++[Production inv tp 0]) []
    rewritten<-mapM (\(r,es)->do
      es'<-mapM (\(p,ll)->do
        let alternatives=[q | v<-versions 1 p,Right q<-[etaLong uniform r(rewrite inv v)],beta q==beta p,Right _<-[summary uniform [] r q]]
            q=if null alternatives then p else snd(minimum [((leafSize q,size q,show q),q) | q<-alternatives])
        pure(q,ll)) es
      pure(r,es')) fs
    (fitted,s)<-objective uniform rewritten 1 1 0.001
    pure(Obj[("grammar",grammarJ fitted),("frontiers",Arr(map frontierInputJ rewritten)),("objective",Num s),("type",typeJ tp)])
  _ -> Core.handleRequest j
  where g=readG(field "grammar" j)
        fs=map readFrontier(arr(field "frontiers" j))
        inv=readP(field "invention" j)

serve handler = do
  hSetBuffering stdout LineBuffering
  let loop = do
        eof<-isEOF
        if eof then pure () else do
          s<-getLine
          let response = case parseJSON s >>= handler of
                Left e->Obj[("ok",Boolean False),("error",Str e)]
                Right r->Obj[("ok",Boolean True),("result",r)]
          result<-try (evaluate (let out=render response in length out `seq` out)) :: IO (Either SomeException String)
          putStrLn(either (\e->render(Obj[("ok",Boolean False),("error",Str(show e))])) id result)
          loop
  loop
main = serve handle
