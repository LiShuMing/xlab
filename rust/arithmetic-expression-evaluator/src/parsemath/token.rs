
#[derive(Debug, PartialEq, Clone)]
pub enum Token {
    Num(f64),
    Add,
    Subtract,
    Multiply,
    Divide,
    EOF,
}