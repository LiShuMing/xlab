open Ocaml_lab

let () =
  Printf.printf "sum of squares [1; 2; 3] = %d\n"
    (Basics.sum_squares [ 1; 2; 3 ]);
  let expression =
    Expr.(Let ("x", Add (Int 2, Int 3), Mul (Var "x", Add (Int 4, Int 5))))
  in
  let optimized = Expr.fold_constants expression in
  Printf.printf "before: %s\nafter:  %s\n" (Expr.to_string expression)
    (Expr.to_string optimized);
  match Expr.eval [] optimized with
  | Ok value -> Printf.printf "result: %d\n" value
  | Error message -> prerr_endline message; exit 1
