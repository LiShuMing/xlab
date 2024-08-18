use std::fmt::Debug;
use std::fmt::Display;
use std::env;

trait HasArea {
    fn area(&self) -> f64;
}

impl HasArea for Rectangle {
    fn area(&self) -> f64 { self.length * self.height }
}

#[derive(Debug)]
struct Rectangle { length: f64, height: f64 }
#[allow(dead_code)]
struct Triangle  { length: f64, height: f64 }

fn print_debug<T: Debug>(t: &T) {
    println!("{:?}", t);
}

fn area<T: HasArea>(t: &T) -> f64 { t.area() }

#[cfg(test)]
pub mod tests {
    use super::*;

    #[test]
    fn test_basic() {
      let rectangle = Rectangle { length: 3.0, height: 4.0 };
      let _triangle = Triangle  { length: 3.0, height: 4.0 };

      print_debug(&rectangle);
      println!("Area: {}", area(&rectangle));

      print_debug(&rectangle);
      let mut v: Vec<i32> = Vec::with_capacity(10);
      for i in 0..10 {
          v.push(i);
      }
      assert_eq!(v[0], 0);
      assert_eq!(v.capacity(), 10);

      env::set_var("RUST_BACKTRACE", "full");
    }
}
