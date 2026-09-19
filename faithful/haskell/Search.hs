module Search where
import Json
import Syntax
import Grammar
import Agenda
import Evaluation
import Data.List (sortOn)

searchTasks g sg request tasks bound depth maxSize budget stateBudget topK =
  let (ps,states,reason)=budgetEnumeration sg [] request bound depth maxSize budget stateBudget
      solve task = do
        let examples=[(arr(field "inputs" e),field "output" e) | e<-arr(field "examples" task)]
            valid p=all (\(xs,y)->evaluateJSON gridPrimitives p xs==Right y) examples
            matches=[(rank,l,p) | (rank,(l,p,_))<-zip[1..]ps,valid p]
        scored<-mapM (\(rank,l,p)->do lp<-logProbability g [] request p;pure(rank,l,p,lp)) matches
        let kept=take topK(sortOn (\(_,_,_,lp)-> -lp) scored)
        f<-frontier g (request,[(p,0) | (_,_,p,_)<-kept])
        pure(Obj[("name",field "name" task),("frontier",frontierJ f),("first_solution_nodes",case matches of (n,_,_):_->Num(fromIntegral n);_->Null),
                 ("solutions",Arr[Obj[("program",progJ p),("search_rank",Num(fromIntegral n)),("search_log_score",Num l),("log_prior",Num lp),("log_likelihood",Num 0)] | (n,l,p,lp)<-kept])])
  in do results<-mapM solve tasks
        pure(Obj[("tasks",Arr results),("enumerated_nodes",Num(fromIntegral(length ps))),("expanded_states",Num(fromIntegral states)),("stop_reason",Str reason)])
