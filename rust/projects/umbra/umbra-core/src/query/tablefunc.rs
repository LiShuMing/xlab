use std::sync::Arc;

use datafusion::datasource::function::TableFunctionImpl;
use datafusion::common::Result as DFResult;
use datafusion::datasource::TableProvider;
use datafusion::execution::context::SessionContext;
use datafusion::logical_expr::Expr;

use crate::UmbraResult;

/// umbra_search(query, top_k, threshold, filters_json) -> table(id, memory, score, ...)
/// Stub implementation — returns an error until full storage wiring is done.
#[derive(Debug)]
pub struct UmbraSearchFunction;

impl UmbraSearchFunction {
    pub fn new() -> Self {
        Self
    }
}

impl TableFunctionImpl for UmbraSearchFunction {
    fn call(&self, _args: &[Expr]) -> DFResult<Arc<dyn TableProvider>> {
        Err(datafusion::error::DataFusionError::NotImplemented(
            "umbra_search not yet implemented".to_string(),
        ))
    }
}

pub fn register_table_functions(ctx: &SessionContext) -> UmbraResult<()> {
    ctx.register_udtf("umbra_search", Arc::new(UmbraSearchFunction::new()));
    Ok(())
}
