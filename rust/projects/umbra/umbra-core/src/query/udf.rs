use std::any::Any;
use std::sync::Arc;

use datafusion::arrow::array::Float64Array;
use datafusion::arrow::datatypes::DataType;
use datafusion::common::Result as DFResult;
use datafusion::execution::context::SessionContext;
use datafusion::logical_expr::{ScalarUDF, ScalarUDFImpl, Signature, TypeSignature, Volatility};
use datafusion::physical_plan::ColumnarValue;

use crate::UmbraResult;

/// Placeholder UDF: cosine_similarity(a, b) -> f64
/// Accepts two FixedSizeBinary(1536) embedding vectors; returns 0.0 until real
/// distance logic is wired.
#[derive(Debug)]
struct CosineSimilarity {
    signature: Signature,
}

impl CosineSimilarity {
    fn new() -> Self {
        Self {
            signature: Signature {
                type_signature: TypeSignature::Exact(vec![
                    DataType::FixedSizeBinary(1536),
                    DataType::FixedSizeBinary(1536),
                ]),
                volatility: Volatility::Immutable,
            },
        }
    }
}

impl ScalarUDFImpl for CosineSimilarity {
    fn as_any(&self) -> &dyn Any {
        self
    }

    fn name(&self) -> &str {
        "cosine_similarity"
    }

    fn signature(&self) -> &Signature {
        &self.signature
    }

    fn return_type(&self, _arg_types: &[DataType]) -> DFResult<DataType> {
        Ok(DataType::Float64)
    }

    fn invoke_batch(
        &self,
        args: &[ColumnarValue],
        number_rows: usize,
    ) -> DFResult<ColumnarValue> {
        if args.len() != 2 {
            return Err(datafusion::error::DataFusionError::Execution(
                "cosine_similarity requires exactly 2 arguments".to_string(),
            ));
        }
        let len = match &args[0] {
            ColumnarValue::Array(a) => a.len(),
            ColumnarValue::Scalar(_) => number_rows,
        };
        Ok(ColumnarValue::Array(Arc::new(Float64Array::from(
            vec![0.0f64; len],
        ))))
    }
}

/// Register all UDFs on the given SessionContext.
pub fn register_udfs(ctx: &SessionContext) -> UmbraResult<()> {
    let cosine = ScalarUDF::new_from_impl(CosineSimilarity::new());
    ctx.register_udf(cosine);

    Ok(())
}
