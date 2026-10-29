import Xlab

set_option autoImplicit false

#guard Xlab.sum [] == 0
#guard Xlab.sum [1, 2, 3] == 6
#guard Xlab.safeHead ([] : List Nat) == none
#guard Xlab.safeHead [7, 8] == some 7
#guard Xlab.Expr.exampleExpr.eval Xlab.Expr.exampleEnv == 45
#guard Xlab.Expr.exampleExpr.foldConstants ==
  Xlab.Expr.mul (.lit 5) (.var "x")

-- This is a universal proof application, in addition to the finite #guard checks.
example (environment : String → Nat) :
    Xlab.Expr.eval environment Xlab.Expr.exampleExpr.foldConstants =
      Xlab.Expr.eval environment Xlab.Expr.exampleExpr :=
  Xlab.Expr.foldConstants_correct _ _

def main : IO Unit := do
  let samples := [Xlab.Expr.lit 0, .var "x", .var "missing", Xlab.Expr.exampleExpr]
  let environments : List (String → Nat) := [fun _ => 0, Xlab.Expr.exampleEnv]
  let mut checks := 0
  for environment in environments do
    for left in samples do
      for right in samples do
        for expression in [Xlab.Expr.add left right, Xlab.Expr.mul left right] do
          if expression.foldConstants.eval environment != expression.eval environment then
            throw (IO.userError "constant folding changed the result")
          checks := checks + 1
  IO.println s!"Lean: {checks} runtime checks, 6 compile-time checks and proofs passed"
