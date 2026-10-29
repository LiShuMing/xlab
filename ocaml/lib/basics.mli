(** Small examples of options, results, higher-order functions, and modules. *)
val sum_squares : int list -> int
val safe_head : 'a list -> 'a option
val safe_divide : int -> int -> (int, string) result
val count_words : string list -> (string * int) list
