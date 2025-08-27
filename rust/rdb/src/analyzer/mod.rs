use crate::parser::ast::Statement;

pub fn analyze(statement: Statement) -> Result<AnalyzedStatement, String> {
    match statement {
        Statement::Select(select) => {
            let analyzed_select = AnalyzedSelect {
                projection: select.projection.into_iter().map(|item| {
                    match item {
                        crate::parser::ast::SelectItem::Wildcard => AnalyzedSelectItem::Wildcard,
                        crate::parser::ast::SelectItem::Expr(expr, alias) => {
                            AnalyzedSelectItem::Expr(analyze_expr(expr), alias)
                        }
                    }
                }).collect(),
                from: select.from,
                selection: select.selection.map(analyze_expr),
            };
            Ok(AnalyzedStatement::Select(analyzed_select))
        }
        _ => Err("Only SELECT statements are supported in this simplified implementation".to_string())
    }
}

fn analyze_expr(expr: crate::parser::ast::Expr) -> AnalyzedExpr {
    match expr {
        crate::parser::ast::Expr::Identifier(ident) => AnalyzedExpr::Identifier(ident),
        crate::parser::ast::Expr::Value(value) => AnalyzedExpr::Value(analyze_value(value)),
        crate::parser::ast::Expr::BinaryOp { left, op, right } => {
            let analyzed_op = match op {
                crate::parser::ast::BinaryOperator::Plus => AnalyzedBinaryOperator::Plus,
                crate::parser::ast::BinaryOperator::Minus => AnalyzedBinaryOperator::Minus,
                crate::parser::ast::BinaryOperator::Multiply => AnalyzedBinaryOperator::Multiply,
                crate::parser::ast::BinaryOperator::Divide => AnalyzedBinaryOperator::Divide,
                crate::parser::ast::BinaryOperator::Eq => AnalyzedBinaryOperator::Eq,
                crate::parser::ast::BinaryOperator::NotEq => AnalyzedBinaryOperator::NotEq,
                crate::parser::ast::BinaryOperator::Lt => AnalyzedBinaryOperator::Lt,
                crate::parser::ast::BinaryOperator::LtEq => AnalyzedBinaryOperator::LtEq,
                crate::parser::ast::BinaryOperator::Gt => AnalyzedBinaryOperator::Gt,
                crate::parser::ast::BinaryOperator::GtEq => AnalyzedBinaryOperator::GtEq,
            };
            
            AnalyzedExpr::BinaryOp {
                left: Box::new(analyze_expr(*left)),
                op: analyzed_op,
                right: Box::new(analyze_expr(*right)),
            }
        }
    }
}

fn analyze_value(value: crate::parser::ast::Value) -> AnalyzedValue {
    match value {
        crate::parser::ast::Value::Integer(i) => AnalyzedValue::Integer(i),
        crate::parser::ast::Value::Text(s) => AnalyzedValue::Text(s),
        crate::parser::ast::Value::Boolean(b) => AnalyzedValue::Boolean(b),
        crate::parser::ast::Value::Null => AnalyzedValue::Null,
    }
}

#[derive(Debug)]
pub enum AnalyzedStatement {
    Select(AnalyzedSelect),
    Insert(AnalyzedInsert),
    CreateTable(AnalyzedCreateTable),
}

#[derive(Debug)]
pub struct AnalyzedSelect {
    pub projection: Vec<AnalyzedSelectItem>,
    pub from: Option<String>,
    pub selection: Option<AnalyzedExpr>,
}

#[derive(Debug)]
pub enum AnalyzedSelectItem {
    Wildcard,
    Expr(AnalyzedExpr, Option<String>),
}

#[derive(Debug)]
pub struct AnalyzedInsert {
    pub table_name: String,
    pub columns: Vec<String>,
    pub values: Vec<Vec<AnalyzedExpr>>,
}

#[derive(Debug)]
pub struct AnalyzedCreateTable {
    pub table_name: String,
    pub columns: Vec<AnalyzedColumnDef>,
}

#[derive(Debug)]
pub struct AnalyzedColumnDef {
    pub name: String,
    pub data_type: AnalyzedDataType,
    pub nullable: bool,
}

#[derive(Debug)]
pub enum AnalyzedDataType {
    Integer,
    Text,
    Boolean,
    Float,
}

#[derive(Debug)]
pub enum AnalyzedExpr {
    Identifier(String),
    Value(AnalyzedValue),
    BinaryOp {
        left: Box<AnalyzedExpr>,
        op: AnalyzedBinaryOperator,
        right: Box<AnalyzedExpr>,
    },
}

#[derive(Debug)]
pub enum AnalyzedValue {
    Integer(i64),
    Text(String),
    Boolean(bool),
    Null,
}

#[derive(Debug)]
pub enum AnalyzedBinaryOperator {
    Plus,
    Minus,
    Multiply,
    Divide,
    Eq,
    NotEq,
    Lt,
    LtEq,
    Gt,
    GtEq,
}