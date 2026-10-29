open Ocaml_lab

let checks = ref 0

let check name expected actual =
  incr checks;
  if expected <> actual then failwith ("check failed: " ^ name)

let () =
  check "sum_squares" 14 (Basics.sum_squares [ 1; 2; 3 ]);
  check "empty sum" 0 (Basics.sum_squares []);
  check "empty head" None (Basics.safe_head []);
  check "polymorphic head" (Some "ocaml") (Basics.safe_head [ "ocaml" ]);
  check "division" (Ok 3) (Basics.safe_divide 7 2);
  check "zero divisor" (Error "division by zero") (Basics.safe_divide 7 0);
  check "word counts" [ ("lean", 1); ("ocaml", 2) ]
    (Basics.count_words [ "ocaml"; "lean"; "ocaml" ]);
  let open Expr in
  check "literal folding" (Int 20)
    (fold_constants (Mul (Add (Int 2, Int 3), Int 4)));
  check "lexical shadowing" (Ok 5)
    (eval [ ("x", 100) ] (Let ("x", Int 5, Var "x")));
  check "binding uses outer environment" (Ok 101)
    (eval [ ("x", 100) ] (Let ("x", Add (Var "x", Int 1), Var "x")));
  check "missing variable" (Error "unbound variable: missing")
    (eval [] (Var "missing"));
  check "multiplication does not erase errors" (Error "unbound variable: missing")
    (eval [] (fold_constants (Mul (Int 0, Var "missing"))));
  let seeds = [ Int 0; Int 2; Var "x"; Var "missing" ] in
  let expressions =
    seeds
    @ List.concat_map
        (fun left ->
          List.concat_map
            (fun right ->
              [ Add (left, right); Mul (left, right); Let ("x", left, right) ])
            seeds)
        seeds
  in
  List.iter
    (fun environment ->
      List.iter
        (fun expression ->
          check "folding preserves values and errors"
            (eval environment expression)
            (eval environment (fold_constants expression)))
        expressions)
    [ []; [ ("x", 7) ] ];
  Printf.printf "OCaml: %d checks passed\n" !checks
