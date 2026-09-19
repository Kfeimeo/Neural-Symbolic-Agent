module DomainMain where
import qualified Bridge
import Syntax
import Json
import Evaluation

listUnary f = Function (\v->case v of Data(Arr xs)->Right(Data(Arr(f xs)));_->Left "Expected list")
binary f = Function(\v->case v of Data(Num x)->Right(numeric(f x));_->Left "Expected number")
primitives = [("incr",numeric (+1)),("incr2",numeric (+2)),
  ("+",binary (+)),("-",binary (-)),("0",Data(Num 0)),("1",Data(Num 1)),
  ("reverse",listUnary reverse),("cdr",listUnary(drop 1)),
  ("map",Function(\f->Right(Function(\v->case v of
    Data(Arr xs)->do
      ys<-mapM (applyValue f . Data) xs
      zs<-mapM (\y->case y of Data j->Right j;_->Left "Function in list") ys
      Right(Data(Arr zs))
    _->Left "Expected list"))))]
handle j = case str(field "operation" j) of
  "evaluate" -> do
    v<-evaluateJSON primitives (readP(field "program" j)) (arr(field "inputs" j))
    pure(Obj[("value",v)])
  "evaluate_batch" -> pure(Obj[("values",Arr[either (const Null) id(evaluateJSON primitives (readP(field "program" j)) (arr xs)) | xs<-arr(field "input_sets" j)])])
  _ -> Bridge.handle j
main = Bridge.serve handle
