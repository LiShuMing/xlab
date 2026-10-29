import Std

set_option autoImplicit false

namespace Xlab

inductive Expr where
  | lit : Nat → Expr
  | var : String → Expr
  | add : Expr → Expr → Expr
  | mul : Expr → Expr → Expr
  deriving Repr, BEq

namespace Expr

def eval (environment : String → Nat) : Expr → Nat
  | .lit value => value
  | .var name => environment name
  | .add left right => eval environment left + eval environment right
  | .mul left right => eval environment left * eval environment right

def smartAdd : Expr → Expr → Expr
  | .lit left, .lit right => .lit (left + right)
  | left, right => .add left right

def smartMul : Expr → Expr → Expr
  | .lit left, .lit right => .lit (left * right)
  | left, right => .mul left right

def foldConstants : Expr → Expr
  | .lit value => .lit value
  | .var name => .var name
  | .add left right => smartAdd (foldConstants left) (foldConstants right)
  | .mul left right => smartMul (foldConstants left) (foldConstants right)

def exampleExpr : Expr := .mul (.add (.lit 2) (.lit 3)) (.var "x")

def exampleEnv (name : String) : Nat := if name == "x" then 9 else 0

end Expr
end Xlab
