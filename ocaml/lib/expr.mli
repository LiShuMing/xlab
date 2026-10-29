(** An immutable expression tree; evaluation explicitly reports missing variables. *)
type t =
  | Int of int
  | Var of string
  | Add of t * t
  | Mul of t * t
  | Let of string * t * t

val eval : (string * int) list -> t -> (int, string) result
val fold_constants : t -> t
val to_string : t -> string
