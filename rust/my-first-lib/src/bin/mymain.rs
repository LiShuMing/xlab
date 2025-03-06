use my_first_lib::add;
use std::borrow::Cow;

const THRESHOLD: i32 = 100;

fn is_big(n: i32) -> bool {
    return n > THRESHOLD;
}

fn apply<F>(f: F)
where
    F: FnOnce(),
{
    f();
}

fn abs_all(input: &mut Cow<'_, [i32]>) {
    for i in 0..input.len() {
        let v = input[i];
        if v < 0 {
            // Clones into a vector if not already owned.
            input.to_mut()[i] = -v;
        }
    }
}

fn main() {
    // Accessing the constant
    let n = 1000;
    println!("{} is {}", n, if is_big(n) { "big" } else { "small" });

    // closure
    let add_one = |x: i32| -> i32 { x + 1 + n };

    // Call the closure with type anonymity
    apply(|| println!("Hello, world!"));

    println!("add_one(1):{}", add_one(1));
    // Call a function from the library
    println!("Going to call libary function");
    let result = add(1, 2);
    println!("result:{}", result);

    // No clone occurs because `input` doesn't need to be mutated.
    let slice = [0, 1, 2];
    let mut input = Cow::from(&slice[..]);
    abs_all(&mut input);

    // Clone occurs because `input` needs to be mutated.
    let slice = [-1, 0, 1];
    let mut input = Cow::from(&slice[..]);
    abs_all(&mut input);

    // No clone occurs because `input` is already owned.
    let mut input = Cow::from(vec![-1, 0, 1]);
    abs_all(&mut input);
}
