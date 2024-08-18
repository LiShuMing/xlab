pub mod ast;

pub fn parse(query: &str) -> Result<ast::Statement, String> {
    // This is a simplified parser that only handles a basic SELECT statement
    // In a real implementation, we would use a proper parsing library like nom or lalrpop
    
    let query = query.trim();
    
    if query.to_uppercase().starts_with("SELECT") {
        parse_select(query)
    } else {
        Err("Only SELECT statements are supported in this simplified parser".to_string())
    }
}

fn parse_select(query: &str) -> Result<ast::Statement, String> {
    // Simplified parsing of SELECT * FROM table_name WHERE condition
    // This is just for demonstration purposes
    
    let parts: Vec<&str> = query.split_whitespace().collect();
    
    if parts.len() < 4 {
        return Err("Invalid SELECT statement".to_string());
    }
    
    // Check if we have SELECT * FROM
    if !parts[0].eq_ignore_ascii_case("SELECT") || 
       parts[1] != "*" || 
       !parts[2].eq_ignore_ascii_case("FROM") {
        return Err("Only SELECT * FROM is supported in this simplified parser".to_string());
    }
    
    let table_name = parts[3].to_string();
    
    // Check if we have a WHERE clause
    let selection = if parts.len() > 5 && parts[4].eq_ignore_ascii_case("WHERE") {
        // Simplified parsing of "id = 1"
        if parts.len() >= 7 {
            let left = ast::Expr::Identifier(parts[5].to_string());
            let right = if let Ok(num) = parts[7].parse::<i64>() {
                ast::Expr::Value(ast::Value::Integer(num))
            } else {
                ast::Expr::Value(ast::Value::Text(parts[7].to_string()))
            };
            
            // For simplicity, we assume all operators are "="
            Some(ast::Expr::BinaryOp {
                left: Box::new(left),
                op: ast::BinaryOperator::Eq,
                right: Box::new(right),
            })
        } else {
            None
        }
    } else {
        None
    };
    
    Ok(ast::Statement::Select(ast::Select {
        projection: vec![ast::SelectItem::Wildcard],
        from: Some(table_name),
        selection,
    }))
}