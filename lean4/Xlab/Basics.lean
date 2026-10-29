import Std

set_option autoImplicit false

namespace Xlab

def sum : List Nat → Nat
  | [] => 0
  | first :: rest => first + sum rest

def safeHead {α : Type} : List α → Option α
  | [] => none
  | first :: _ => some first

theorem sum_append (left right : List Nat) :
    sum (left ++ right) = sum left + sum right := by
  induction left with
  | nil => simp [sum]
  | cons first rest ih => simp [sum, ih, Nat.add_assoc]

end Xlab
