#[derive(Debug, Clone, PartialEq)]
pub enum Statement {
    Select(Select),
    Insert(Insert),
    CreateTable(CreateTable),
    // Other SQL statements can be added here
}

#[derive(Debug, Clone, PartialEq)]
pub struct Select {
    pub projection: Vec<SelectItem>,
    pub from: Option<String>,
    pub selection: Option<Expr>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum SelectItem {
    Wildcard,
    Expr(Expr, Option<String>), // expression and optional alias
}

#[derive(Debug, Clone, PartialEq)]
pub struct Insert {
    pub table_name: String,
    pub columns: Vec<String>,
    pub values: Vec<Vec<Expr>>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct CreateTable {
    pub table_name: String,
    pub columns: Vec<ColumnDef>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ColumnDef {
    pub name: String,
    pub data_type: DataType,
    pub nullable: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub enum DataType {
    Integer,
    Text,
    Boolean,
    Float,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Identifier(String),
    Value(Value),
    BinaryOp {
        left: Box<Expr>,
        op: BinaryOperator,
        right: Box<Expr>,
    },
    // Other expression types can be added here
}

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Integer(i64),
    Text(String),
    Boolean(bool),
    Null,
}

#[derive(Debug, Clone, PartialEq)]
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