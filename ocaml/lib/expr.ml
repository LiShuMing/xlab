type t =
  | Int of int
  | Var of string
  | Add of t * t
  | Mul of t * t
  | Let of string * t * t

let ( let* ) = Result.bind

let rec eval environment = function
  | Int value -> Ok value
  | Var name -> (
      match List.assoc_opt name environment with
      | Some value -> Ok value
      | None -> Error ("unbound variable: " ^ name))
  | Add (left, right) ->
      let* left_value = eval environment left in
      let* right_value = eval environment right in
      Ok (left_value + right_value)
  | Mul (left, right) ->
      let* left_value = eval environment left in
      let* right_value = eval environment right in
      Ok (left_value * right_value)
  | Let (name, value, body) ->
      let* bound_value = eval environment value in
      eval ((name, bound_value) :: environment) body

let rec fold_constants = function
  | (Int _ | Var _) as expression -> expression
  | Add (left, right) -> (
      match (fold_constants left, fold_constants right) with
      | Int a, Int b -> Int (a + b)
      | left, right -> Add (left, right))
  | Mul (left, right) -> (
      match (fold_constants left, fold_constants right) with
      | Int a, Int b -> Int (a * b)
      | left, right -> Mul (left, right))
  | Let (name, value, body) ->
      Let (name, fold_constants value, fold_constants body)

let rec to_string = function
  | Int value -> string_of_int value
  | Var name -> name
  | Add (left, right) ->
      Printf.sprintf "(%s + %s)" (to_string left) (to_string right)
  | Mul (left, right) ->
      Printf.sprintf "(%s * %s)" (to_string left) (to_string right)
  | Let (name, value, body) ->
      Printf.sprintf "(let %s = %s in %s)" name (to_string value) (to_string body)
