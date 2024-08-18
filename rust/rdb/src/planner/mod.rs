use crate::analyzer::AnalyzedStatement;

pub fn plan(statement: AnalyzedStatement) -> Result<LogicalPlan, String> {
    match statement {
        AnalyzedStatement::Select(select) => {
            // Create a scan of the table
            let mut plan = LogicalPlan::Scan {
                table_name: select.from.unwrap_or_default(),
                projection: None, // For now, we'll scan all columns
            };
            
            // If there's a selection clause, add a selection node
            if let Some(selection) = select.selection {
                plan = LogicalPlan::Selection {
                    expr: plan_expr(selection),
                    input: Box::new(plan),
                };
            }
            
            // Add a projection node
            let proj_exprs = select.projection.into_iter().map(|item| {
                match item {
                    crate::analyzer::AnalyzedSelectItem::Wildcard => {
                        // For simplicity, we'll just use a placeholder
                        // In a real implementation, we would expand the wildcard
                        Expr::Column(0)
                    }
                    crate::analyzer::AnalyzedSelectItem::Expr(expr, _) => {
                        plan_expr(expr)
                    }
                }
            }).collect();
            
            plan = LogicalPlan::Projection {
                expr: proj_exprs,
                input: Box::new(plan),
            };
            
            Ok(plan)
        }
        _ => Err("Only SELECT statements are supported in this simplified implementation".to_string())
    }
}

fn plan_expr(expr: crate::analyzer::AnalyzedExpr) -> Expr {
    match expr {
        crate::analyzer::AnalyzedExpr::Identifier(_) => {
            // For simplicity, we'll just use a placeholder column index
            // In a real implementation, we would resolve the identifier to a column
            Expr::Column(0)
        }
        crate::analyzer::AnalyzedExpr::Value(value) => {
            Expr::Value(plan_value(value))
        }
        crate::analyzer::AnalyzedExpr::BinaryOp { left, op, right } => {
            let planned_op = match op {
                crate::analyzer::AnalyzedBinaryOperator::Plus => BinaryOperator::Plus,
                crate::analyzer::AnalyzedBinaryOperator::Minus => BinaryOperator::Minus,
                crate::analyzer::AnalyzedBinaryOperator::Multiply => BinaryOperator::Multiply,
                crate::analyzer::AnalyzedBinaryOperator::Divide => BinaryOperator::Divide,
                crate::analyzer::AnalyzedBinaryOperator::Eq => BinaryOperator::Eq,
                crate::analyzer::AnalyzedBinaryOperator::NotEq => BinaryOperator::NotEq,
                crate::analyzer::AnalyzedBinaryOperator::Lt => BinaryOperator::Lt,
                crate::analyzer::AnalyzedBinaryOperator::LtEq => BinaryOperator::LtEq,
                crate::analyzer::AnalyzedBinaryOperator::Gt => BinaryOperator::Gt,
                crate::analyzer::AnalyzedBinaryOperator::GtEq => BinaryOperator::GtEq,
            };
            
            Expr::BinaryOp {
                left: Box::new(plan_expr(*left)),
                op: planned_op,
                right: Box::new(plan_expr(*right)),
            }
        }
    }
}

fn plan_value(value: crate::analyzer::AnalyzedValue) -> Value {
    match value {
        crate::analyzer::AnalyzedValue::Integer(i) => Value::Integer(i),
        crate::analyzer::AnalyzedValue::Text(s) => Value::Text(s),
        crate::analyzer::AnalyzedValue::Boolean(b) => Value::Boolean(b),
        crate::analyzer::AnalyzedValue::Null => Value::Null,
    }
}

#[derive(Debug)]
pub enum LogicalPlan {
    Projection {
        expr: Vec<Expr>,
        input: Box<LogicalPlan>,
    },
    Selection {
        expr: Expr,
        input: Box<LogicalPlan>,
    },
    Scan {
        table_name: String,
        projection: Option<Vec<usize>>, // column indices
    },
    CreateTable {
        table_name: String,
        columns: Vec<ColumnDef>,
    },
    Insert {
        table_name: String,
        columns: Vec<String>,
        values: Vec<Vec<Expr>>,
    },
}

#[derive(Debug)]
pub struct ColumnDef {
    pub name: String,
    pub data_type: DataType,
    pub nullable: bool,
}

#[derive(Debug)]
pub enum DataType {
    Integer,
    Text,
    Boolean,
    Float,
}

#[derive(Debug)]
pub enum Expr {
    Column(usize), // column index
    Value(Value),
    BinaryOp {
        left: Box<Expr>,
        op: BinaryOperator,
        right: Box<Expr>,
    },
}

#[derive(Debug)]
pub enum Value {
    Integer(i64),
    Text(String),
    Boolean(bool),
    Null,
}

#[derive(Debug)]
pub enum BinaryOperator {
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