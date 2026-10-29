import Xlab

def main : IO Unit := do
  IO.println s!"sum [1, 2, 3] = {Xlab.sum [1, 2, 3]}"
  let expression := Xlab.Expr.exampleExpr
  let optimized := expression.foldConstants
  IO.println s!"before: {repr expression}"
  IO.println s!"after:  {repr optimized}"
  IO.println s!"result: {optimized.eval Xlab.Expr.exampleEnv}"
  IO.println "foldConstants_correct: checked during the library build"
