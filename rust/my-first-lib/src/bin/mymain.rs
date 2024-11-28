use my_first_lib::add;

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
}
