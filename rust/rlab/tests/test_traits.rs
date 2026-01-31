//! Trait system demonstrations
//!
//! These tests demonstrate Rust's trait system:
//! - Defining traits
//! - Implementing traits for types
//! - Generic functions with trait bounds
//! - Debug and Display traits

use std::fmt::Debug;
use std::fmt::Display;

/// A trait for types that have an area
trait HasArea {
    /// Calculate the area of the shape
    fn area(&self) -> f64;
    
    /// Check if the shape has any area
    fn has_positive_area(&self) -> bool {
        self.area() > 0.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
struct Rectangle {
    length: f64,
    height: f64,
}

impl Rectangle {
    fn new(length: f64, height: f64) -> Self {
        Rectangle { length, height }
    }
    
    fn is_square(&self) -> bool {
        (self.length - self.height).abs() < f64::EPSILON
    }
}

impl HasArea for Rectangle {
    fn area(&self) -> f64 {
        self.length * self.height
    }
}

impl Display for Rectangle {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Rectangle({} x {})", self.length, self.height)
    }
}

#[derive(Debug)]
#[allow(dead_code)]
struct Triangle {
    base: f64,
    height: f64,
}

impl Triangle {
    fn new(base: f64, height: f64) -> Self {
        Triangle { base, height }
    }
}

impl HasArea for Triangle {
    fn area(&self) -> f64 {
        0.5 * self.base * self.height
    }
}

/// Generic function that works with any Debug type
#[allow(dead_code)]
fn print_debug<T: Debug>(t: &T) {
    println!("{:?}", t);
}

/// Generic function that requires HasArea trait
fn area<T: HasArea>(t: &T) -> f64 {
    t.area()
}

/// Function with multiple trait bounds
fn describe_shape<T>(t: &T) -> String
where
    T: HasArea + Debug + Display,
{
    format!("{} with area {}", t, area(t))
}

#[test]
fn test_rectangle_area() {
    let rectangle = Rectangle::new(3.0, 4.0);
    assert_eq!(rectangle.area(), 12.0);
    assert!(rectangle.has_positive_area());
}

#[test]
fn test_rectangle_is_square() {
    let square = Rectangle::new(5.0, 5.0);
    assert!(square.is_square());
    
    let rect = Rectangle::new(5.0, 4.0);
    assert!(!rect.is_square());
}

#[test]
fn test_triangle_area() {
    let triangle = Triangle::new(3.0, 4.0);
    assert_eq!(triangle.area(), 6.0);
}

#[test]
fn test_generic_area() {
    let rect = Rectangle::new(3.0, 4.0);
    let tri = Triangle::new(3.0, 4.0);
    
    assert_eq!(area(&rect), 12.0);
    assert_eq!(area(&tri), 6.0);
}

#[test]
fn test_display_trait() {
    let rect = Rectangle::new(3.0, 4.0);
    let display = format!("{}", rect);
    assert_eq!(display, "Rectangle(3 x 4)");
}

#[test]
fn test_describe_shape() {
    let rect = Rectangle::new(3.0, 4.0);
    let description = describe_shape(&rect);
    assert!(description.contains("Rectangle"));
    assert!(description.contains("12"));
}

#[test]
fn test_vector_operations() {
    let mut v: Vec<i32> = Vec::with_capacity(10);
    
    // Push elements
    for i in 0..5 {
        v.push(i);
    }
    
    assert_eq!(v.len(), 5);
    assert_eq!(v.capacity(), 10);
    assert_eq!(v[0], 0);
    assert_eq!(v[4], 4);
}
