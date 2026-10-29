import Xlab.Expr

set_option autoImplicit false

namespace Xlab.Expr

theorem eval_smartAdd (environment : String → Nat) (left right : Expr) :
    eval environment (smartAdd left right) =
      eval environment left + eval environment right := by
  cases left <;> cases right <;> rfl

theorem eval_smartMul (environment : String → Nat) (left right : Expr) :
    eval environment (smartMul left right) =
      eval environment left * eval environment right := by
  cases left <;> cases right <;> rfl

theorem foldConstants_correct (expression : Expr) (environment : String → Nat) :
    eval environment (foldConstants expression) = eval environment expression := by
  induction expression with
  | lit value => rfl
  | var name => rfl
  | add left right ihLeft ihRight =>
      simp only [foldConstants, eval_smartAdd, eval, ihLeft, ihRight]
  | mul left right ihLeft ihRight =>
      simp only [foldConstants, eval_smartMul, eval, ihLeft, ihRight]

end Xlab.Expr
