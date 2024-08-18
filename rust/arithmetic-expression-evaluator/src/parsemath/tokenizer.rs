
use std::iter::Peekable;
use std::str::Chars;

use super::token::Token;

pub struct Tokenizer<'a> {
    expr: Peekable<Chars<'a>>
}

impl<'a> Tokenizer<'a> {
    pub fn new(new_expr: &'a str) -> Self {
        Tokenizer {
            expr : new_expr.chars().peekable(),
        }
    }
}

impl<'a> Iterator for Tokenizer<'a> {
    type Item = Token;

    fn next(&mut self) -> Option<Self::Item> {
        let next = self.expr.next();
        match next {
            Some('0'..='9') => {
                let mut number = next?.to_string();
                while let Some(next) = self.expr.peek() {
                    if next.is_numeric() || next == &'.' {
                        number.push(self.expr.next()?);
                    } else if next == &'(' {
                        return None;
                    } else {
                        break;
                    }
                }
                Some(Token::Num(number.parse::<f64>().unwrap()))
            }
            Some('+') => Some(Token::Add),
            Some('-') => Some(Token::Subtract),
            Some('*') => Some(Token::Multiply),
            Some('/') => Some(Token::Divide),
            None => Some(Token::EOF),
            Some(_)=> None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_positive_integer() {
        let mut tokenizer = Tokenizer::new("1234");
        assert_eq!(tokenizer.next().unwrap(), Token::Num(1234.0))
    }
}