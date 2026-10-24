/// Build a `Vec<String>` from string literals, e.g. `vec_string!["a", "b"]`.
#[macro_export]
macro_rules! vec_string {
    ($($e:expr),*) => {vec![$($e.to_owned()), *]};
    ($($e:expr,)*) => {vec![$($e.to_owned()), *]};
}
