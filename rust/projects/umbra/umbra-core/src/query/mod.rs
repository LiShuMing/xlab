use datafusion::execution::context::SessionContext;

use crate::UmbraResult;

pub mod tablefunc;
pub mod udf;

/// Register all umbra tables, UDTFs, and UDFs on a DataFusion SessionContext.
pub fn register_all(ctx: &SessionContext) -> UmbraResult<()> {
    udf::register_udfs(ctx)?;
    tablefunc::register_table_functions(ctx)?;
    Ok(())
}
