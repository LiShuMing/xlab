let sum_squares values =
  List.fold_left (fun total value -> total + (value * value)) 0 values

let safe_head = function [] -> None | first :: _ -> Some first

let safe_divide numerator denominator =
  if denominator = 0 then Error "division by zero"
  else Ok (numerator / denominator)

module Word_map = Map.Make (String)

let count_words words =
  let add_word counts word =
    Word_map.update word
      (function None -> Some 1 | Some count -> Some (count + 1))
      counts
  in
  List.fold_left add_word Word_map.empty words |> Word_map.bindings
