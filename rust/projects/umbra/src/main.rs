//! Umbra-inspired JIT Compilation PoC
//! 
//! This Proof of Concept demonstrates a data-centric JIT compilation pipeline
//! for OLAP query execution, inspired by systems like Umbra and DuckDB.
//! 
//! Architecture Overview:
//! - Columnar data representation using Vec<i64>
//! - AST-based expression representation (Expr enum)
//! - Cranelift-based JIT compiler that translates AST to native machine code
//! - Batch-oriented execution model

use cranelift::prelude::*;
use cranelift_frontend::{FunctionBuilder, FunctionBuilderContext};
use cranelift_jit::{JITBuilder, JITModule};
use cranelift_module::{Linkage, Module};
use std::mem;

/// =============================================================================
/// SECTION 1: AST Definition
/// =============================================================================

/// Abstract Syntax Tree representing SQL expressions.
/// 
/// This enum models a simple expression language supporting:
/// - Column references (ColumnA, ColumnB) - indices into input arrays
/// - Arithmetic operations (Add, Mul) - binary operations on expressions
/// 
/// Example expression: A * B + A
/// Expr::Add(
///     Box::new(Expr::Mul(Box::new(Expr::ColumnA), Box::new(Expr::ColumnB))),
///     Box::new(Expr::ColumnA)
/// )
#[derive(Debug, Clone)]
#[non_exhaustive]
pub enum Expr {
    /// Reference to the first input column (Column A)
    ColumnA,
    /// Reference to the second input column (Column B)
    ColumnB,
    /// Binary addition of two expressions
    Add(Box<Expr>, Box<Expr>),
    /// Binary multiplication of two expressions
    Mul(Box<Expr>, Box<Expr>),
}

impl Expr {
    /// Creates an addition expression
    fn add(lhs: Expr, rhs: Expr) -> Self {
        Expr::Add(Box::new(lhs), Box::new(rhs))
    }

    /// Creates a multiplication expression
    fn mul(lhs: Expr, rhs: Expr) -> Self {
        Expr::Mul(Box::new(lhs), Box::new(rhs))
    }
}

/// =============================================================================
/// SECTION 2: JIT Compiler Core
/// =============================================================================

/// JIT compiler managing the Cranelift infrastructure.
/// 
/// This struct encapsulates all state required for JIT compilation:
/// - `module`: The JITModule handles function compilation and memory management
/// - `ctx`: The CompilationContext stores function-level compilation state
/// - `builder_ctx`: FunctionBuilderContext for constructing Cranelift IR
/// 
/// The JIT compiler follows a data-centric code generation model where
/// the generated code iterates over columnar data in tight loops.
pub struct JIT {
    /// The JITModule manages compiled functions and their memory
    module: JITModule,
    /// Compilation context for building functions
    ctx: codegen::Context,
    /// Context for the FunctionBuilder (reused across compilations for efficiency)
    builder_ctx: FunctionBuilderContext,
}

impl JIT {
    /// Creates a new JIT compiler instance.
    /// 
    /// Initializes the Cranelift backend with native target settings
    /// and creates the JITModule for function compilation.
    pub fn new() -> Result<Self, String> {
        // Configure the Cranelift flag builder with native settings
        let flag_builder = settings::builder();
        
        // Create the ISA (Instruction Set Architecture) builder for the native target
        let isa_builder = match cranelift_native::builder() {
            Ok(isa_builder) => isa_builder,
            Err(err) => return Err(format!("Failed to create ISA builder: {}", err)),
        };
        
        // Finalize the ISA with our flags
        let isa = isa_builder
            .finish(settings::Flags::new(flag_builder))
            .map_err(|e| format!("Failed to create ISA: {}", e))?;
        
        // Create the JIT module builder
        let builder = JITBuilder::with_isa(isa, cranelift_module::default_libcall_names());
        
        // Build the JIT module
        let module = JITModule::new(builder);
        
        Ok(Self {
            module,
            ctx: codegen::Context::new(),
            builder_ctx: FunctionBuilderContext::new(),
        })
    }

    /// Compiles an expression AST into native machine code.
    /// 
    /// The generated function has the following signature (System V AMD64 ABI):
    /// ```c
    /// void compute_batch(
    ///     const int64_t* col_a,  // %rdi - first input column pointer
    ///     const int64_t* col_b,  // %rsi - second input column pointer
    ///     int64_t* output,       // %rdx - output buffer pointer
    ///     size_t row_count       // %rcx - number of rows to process
    /// );
    /// ```
    /// 
    /// # Arguments
    /// * `expr` - The expression AST to compile
    /// 
    /// # Returns
    /// A raw pointer to the compiled function
    pub fn compile(&mut self, expr: &Expr) -> Result<*const u8, String> {
        // Clear any previous compilation state
        self.ctx.clear();
        
        // =====================================================================
        // STEP 1: Define the Function Signature
        // =====================================================================
        
        // Create a new function signature with the System V calling convention
        let mut sig = self.module.make_signature();
        
        // Parameter 0: col_a - pointer to first input column (*const i64)
        sig.params.push(AbiParam::new(types::I64));
        // Parameter 1: col_b - pointer to second input column (*const i64)
        sig.params.push(AbiParam::new(types::I64));
        // Parameter 2: output - pointer to output buffer (*mut i64)
        sig.params.push(AbiParam::new(types::I64));
        // Parameter 3: row_count - number of rows to process (usize)
        sig.params.push(AbiParam::new(types::I64));
        
        // No return value (void function)
        
        // =====================================================================
        // STEP 2: Create Function Builder
        // =====================================================================
        
        // Build the function declaration
        let func_id = self
            .module
            .declare_function("compute_batch", Linkage::Local, &sig)
            .map_err(|e| format!("Failed to declare function: {}", e))?;
        
        // Associate the signature with our compilation context
        self.ctx.func.signature = sig;
        
        // Create the FunctionBuilder which is the primary API for constructing IR
        let mut builder = FunctionBuilder::new(&mut self.ctx.func, &mut self.builder_ctx);
        
        // Create the entry basic block
        let entry_block = builder.create_block();
        
        // Append function parameters to the entry block
        // This connects the function signature's parameters to the entry block
        builder.append_block_params_for_function_params(entry_block);
        
        // Create the loop body block (where the actual computation happens)
        let loop_block = builder.create_block();
        
        // Create the exit block (return point)
        let exit_block = builder.create_block();
        
        // =====================================================================
        // STEP 3: Emit Entry Block (Parameter Extraction)
        // =====================================================================
        
        // Switch to the entry block
        builder.switch_to_block(entry_block);
        
        // Mark the entry block as the function's entry point
        builder.seal_block(entry_block);
        
        // Extract function parameters as Cranelift Value handles
        // These correspond to the registers/stack slots passed by the caller
        // The params were appended by append_block_params_for_function_params above
        let col_a_ptr = builder.block_params(entry_block)[0]; // %rdi
        let col_b_ptr = builder.block_params(entry_block)[1]; // %rsi
        let output_ptr = builder.block_params(entry_block)[2]; // %rdx
        let row_count = builder.block_params(entry_block)[3]; // %rcx
        
        // =====================================================================
        // STEP 4: Variable Declaration
        // =====================================================================
        
        // Declare mutable variables using Cranelift's variable system.
        // Variables are SSA values that can be mutated across blocks.
        
        // Index variable for the loop (starts at 0)
        let var_idx = Variable::new(0);
        builder.declare_var(var_idx, types::I64);
        
        // Current position pointers for each column (updated each iteration)
        let var_a_ptr = Variable::new(1);
        builder.declare_var(var_a_ptr, types::I64);
        
        let var_b_ptr = Variable::new(2);
        builder.declare_var(var_b_ptr, types::I64);
        
        let var_out_ptr = Variable::new(3);
        builder.declare_var(var_out_ptr, types::I64);
        
        // Initialize variables with starting values
        let zero = builder.ins().iconst(types::I64, 0);
        builder.def_var(var_idx, zero);
        builder.def_var(var_a_ptr, col_a_ptr);
        builder.def_var(var_b_ptr, col_b_ptr);
        builder.def_var(var_out_ptr, output_ptr);
        
        // =====================================================================
        // STEP 5: Loop Control Flow Setup
        // =====================================================================
        
        // Branch to the loop block if row_count > 0, otherwise go to exit
        // We use unsigned comparison for row_count
        builder.ins().brif(row_count, loop_block, &[], exit_block, &[]);
        
        // =====================================================================
        // STEP 6: Emit Loop Body Block (The Core Computation)
        // =====================================================================
        
        builder.switch_to_block(loop_block);
        
        // Load current variable values
        let idx = builder.use_var(var_idx);
        let current_a_ptr = builder.use_var(var_a_ptr);
        let current_b_ptr = builder.use_var(var_b_ptr);
        let current_out_ptr = builder.use_var(var_out_ptr);
        
        // -----------------------------------------------------------------
        // Memory Load Operations
        // -----------------------------------------------------------------
        
        // MemFlags controls memory access semantics:
        // - `new()` creates default flags
        // - `with_aligned()` indicates the memory is properly aligned (8 bytes for i64)
        // - `with_notrap()` indicates this load cannot cause a trap (no page fault expected)
        // These flags enable the optimizer to generate more efficient load instructions
        
        let mut flags = MemFlags::new();
        flags.set_aligned();
        flags.set_notrap();
        
        // Load values from column buffers: *ptr
        let val_a = builder.ins().load(types::I64, flags, current_a_ptr, 0);
        let val_b = builder.ins().load(types::I64, flags, current_b_ptr, 0);
        
        // -----------------------------------------------------------------
        // Expression Evaluation (AST Traversal)
        // -----------------------------------------------------------------
        
        // Recursively traverse the AST and generate computation instructions
        let result = Self::compile_expr(expr, &mut builder, val_a, val_b)?;
        
        // -----------------------------------------------------------------
        // Memory Store Operation
        // -----------------------------------------------------------------
        
        // Store the computed result to the output buffer
        builder.ins().store(flags, result, current_out_ptr, 0);
        
        // -----------------------------------------------------------------
        // Pointer Arithmetic (Advance to next row)
        // -----------------------------------------------------------------
        
        // Calculate pointer stride: sizeof(i64) = 8 bytes
        let stride = builder.ins().iconst(types::I64, 8);
        
        // Advance each pointer by one element (8 bytes)
        let next_a_ptr = builder.ins().iadd(current_a_ptr, stride);
        let next_b_ptr = builder.ins().iadd(current_b_ptr, stride);
        let next_out_ptr = builder.ins().iadd(current_out_ptr, stride);
        
        // Update pointer variables
        builder.def_var(var_a_ptr, next_a_ptr);
        builder.def_var(var_b_ptr, next_b_ptr);
        builder.def_var(var_out_ptr, next_out_ptr);
        
        // -----------------------------------------------------------------
        // Loop Counter Update and Branch
        // -----------------------------------------------------------------
        
        // Increment the loop index
        let one = builder.ins().iconst(types::I64, 1);
        let next_idx = builder.ins().iadd(idx, one);
        builder.def_var(var_idx, next_idx);
        
        // Check if we've processed all rows: idx < row_count
        // If true, continue looping; if false, exit
        let cmp = builder.ins().icmp(IntCC::UnsignedLessThan, next_idx, row_count);
        builder.ins().brif(cmp, loop_block, &[], exit_block, &[]);
        
        // Seal the loop block (no more predecessors will be added)
        builder.seal_block(loop_block);
        
        // =====================================================================
        // STEP 7: Emit Exit Block (Function Return)
        // =====================================================================
        
        builder.switch_to_block(exit_block);
        
        // Return void
        builder.ins().return_(&[]);
        
        // Seal the exit block
        builder.seal_block(exit_block);
        
        // =====================================================================
        // STEP 8: Finalize and Compile
        // =====================================================================
        
        // Finalize the function builder (validates SSA form, etc.)
        builder.finalize();
        
        // Compile the function
        self.module
            .define_function(func_id, &mut self.ctx)
            .map_err(|e| format!("Failed to define function: {}", e))?;
        
        // Finalize module definitions (commits to memory)
        self.module
            .finalize_definitions()
            .map_err(|e| format!("Failed to finalize definitions: {}", e))?;
        
        // Get the raw pointer to the compiled code
        let code_ptr = self.module.get_finalized_function(func_id);
        
        Ok(code_ptr)
    }

    /// Recursively compiles an expression AST into Cranelift IR.
    /// 
    /// This method traverses the AST and generates the appropriate arithmetic
    /// instructions using Cranelift's builder API.
    /// 
    /// # Arguments
    /// * `expr` - The expression to compile
    /// * `builder` - The function builder for emitting instructions
    /// * `val_a` - Cranelift Value representing Column A's current element
    /// * `val_b` - Cranelift Value representing Column B's current element
    /// 
    /// # Returns
    /// The Cranelift Value representing the computed result
    fn compile_expr(
        expr: &Expr,
        builder: &mut FunctionBuilder,
        val_a: Value,
        val_b: Value,
    ) -> Result<Value, String> {
        match expr {
            // Column references simply return the loaded values
            Expr::ColumnA => Ok(val_a),
            Expr::ColumnB => Ok(val_b),
            
            // Addition: recursively compile both sides, then add
            Expr::Add(lhs, rhs) => {
                let left = Self::compile_expr(lhs, builder, val_a, val_b)?;
                let right = Self::compile_expr(rhs, builder, val_a, val_b)?;
                Ok(builder.ins().iadd(left, right))
            }
            
            // Multiplication: recursively compile both sides, then multiply
            Expr::Mul(lhs, rhs) => {
                let left = Self::compile_expr(lhs, builder, val_a, val_b)?;
                let right = Self::compile_expr(rhs, builder, val_a, val_b)?;
                Ok(builder.ins().imul(left, right))
            }
        }
    }
}

/// =============================================================================
/// SECTION 3: Main Entry Point
/// =============================================================================

fn main() {
    println!("============================================================");
    println!("  Umbra-inspired JIT Compilation PoC");
    println!("  Data-centric code generation for OLAP expressions");
    println!("============================================================\n");
    
    // =====================================================================
    // STEP 1: Prepare Test Data (Columnar Format)
    // =====================================================================
    
    // Number of rows to process in the batch
    const ROW_COUNT: usize = 10;
    
    // Initialize column data as contiguous arrays (columnar storage)
    // Column A: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    let col_a: Vec<i64> = (1..=ROW_COUNT as i64).collect();
    
    // Column B: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    let col_b: Vec<i64> = (1..=ROW_COUNT as i64).map(|x| x * 10).collect();
    
    // Output buffer (uninitialized)
    let mut output: Vec<i64> = vec![0; ROW_COUNT];
    
    println!("Input Data:");
    println!("  Column A: {:?}", col_a);
    println!("  Column B: {:?}", col_b);
    println!();
    
    // =====================================================================
    // STEP 2: Define the Expression AST
    // =====================================================================
    
    // Build the expression: A * B + A
    // This corresponds to SQL: col_a * col_b + col_a
    let expr = Expr::add(Expr::mul(Expr::ColumnA, Expr::ColumnB), Expr::ColumnA);
    
    println!("Expression: A * B + A");
    println!("Expected results: [11, 42, 93, 164, 255, 366, 497, 648, 819, 1010]");
    println!();
    
    // =====================================================================
    // STEP 3: Initialize JIT Compiler
    // =====================================================================
    
    let mut jit = JIT::new().expect("Failed to create JIT compiler");
    
    // =====================================================================
    // STEP 4: Compile Expression to Native Code
    // =====================================================================
    
    println!("Compiling expression to native machine code...");
    let code_ptr = jit.compile(&expr).expect("Failed to compile expression");
    println!("Compilation successful! Code at: {:p}\n", code_ptr);
    
    // =====================================================================
    // STEP 5: Execute JIT-compiled Function
    // =====================================================================
    
    // Define the function signature for the compiled code
    // Using extern "C" to match the System V AMD64 ABI used by Cranelift
    type ComputeFn = extern "C" fn(*const i64, *const i64, *mut i64, usize);
    
    // SAFETY: Transmuting a raw pointer to a function pointer is unsafe because
    // the compiler cannot verify that the pointer actually points to valid code
    // with the correct signature. We know this is safe because:
    // 1. The JIT compiler just successfully compiled the function
    // 2. We defined the signature to match exactly what we generated
    // 3. The function has the System V AMD64 ABI which matches extern "C"
    let compute_fn: ComputeFn = unsafe { mem::transmute(code_ptr) };
    
    println!("Executing JIT-compiled batch function...");
    
    // Execute the JIT-compiled function with our data
    // Note: Calling an extern "C" fn function pointer is safe in Rust 2021 edition.
    // The safety invariants were established when we transmuted the code pointer,
    // and the pointers passed are valid, properly aligned, and live for the call.
    compute_fn(
        col_a.as_ptr(),      // Pointer to column A data
        col_b.as_ptr(),      // Pointer to column B data
        output.as_mut_ptr(), // Pointer to output buffer
        ROW_COUNT,           // Number of rows to process
    );
    
    println!("Execution complete!\n");
    
    // =====================================================================
    // STEP 6: Verify Results
    // =====================================================================
    
    println!("Results:");
    println!("  Output:   {:?}", output);
    
    // Calculate expected values for verification
    let expected: Vec<i64> = col_a
        .iter()
        .zip(col_b.iter())
        .map(|(a, b)| a * b + a)
        .collect();
    
    println!("  Expected: {:?}", expected);
    
    // Verify correctness
    assert_eq!(
        output, expected,
        "JIT output does not match expected values!"
    );
    
    println!("\n✓ All assertions passed! JIT compilation and execution successful.");
    
    // Additional sanity checks
    for (i, (&out, &exp)) in output.iter().zip(expected.iter()).enumerate() {
        assert_eq!(
            out, exp,
            "Mismatch at row {}: got {}, expected {}",
            i, out, exp
        );
    }
    
    println!("✓ Row-by-row verification passed!");
}

/// =============================================================================
/// SECTION 4: Unit Tests
/// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// Test basic expression evaluation through JIT
    #[test]
    fn test_jit_add() {
        let mut jit = JIT::new().unwrap();
        let expr = Expr::add(Expr::ColumnA, Expr::ColumnB);
        
        let col_a = vec![1i64, 2, 3];
        let col_b = vec![10i64, 20, 30];
        let mut output = vec![0i64; 3];
        
        let code_ptr = jit.compile(&expr).unwrap();
        type ComputeFn = extern "C" fn(*const i64, *const i64, *mut i64, usize);
        let compute_fn: ComputeFn = unsafe { mem::transmute(code_ptr) };
        
        compute_fn(col_a.as_ptr(), col_b.as_ptr(), output.as_mut_ptr(), 3);
        
        assert_eq!(output, vec![11, 22, 33]);
    }

    /// Test multiplication expression
    #[test]
    fn test_jit_mul() {
        let mut jit = JIT::new().unwrap();
        let expr = Expr::mul(Expr::ColumnA, Expr::ColumnB);
        
        let col_a = vec![2i64, 3, 4];
        let col_b = vec![5i64, 6, 7];
        let mut output = vec![0i64; 3];
        
        let code_ptr = jit.compile(&expr).unwrap();
        type ComputeFn = extern "C" fn(*const i64, *const i64, *mut i64, usize);
        let compute_fn: ComputeFn = unsafe { mem::transmute(code_ptr) };
        
        compute_fn(col_a.as_ptr(), col_b.as_ptr(), output.as_mut_ptr(), 3);
        
        assert_eq!(output, vec![10, 18, 28]);
    }

    /// Test combined expression: A * B + A
    #[test]
    fn test_jit_complex_expr() {
        let mut jit = JIT::new().unwrap();
        let expr = Expr::add(Expr::mul(Expr::ColumnA, Expr::ColumnB), Expr::ColumnA);
        
        let col_a = vec![1i64, 2, 3];
        let col_b = vec![10i64, 20, 30];
        let mut output = vec![0i64; 3];
        
        let code_ptr = jit.compile(&expr).unwrap();
        type ComputeFn = extern "C" fn(*const i64, *const i64, *mut i64, usize);
        let compute_fn: ComputeFn = unsafe { mem::transmute(code_ptr) };
        
        compute_fn(col_a.as_ptr(), col_b.as_ptr(), output.as_mut_ptr(), 3);
        
        // A * B + A = [1*10+1, 2*20+2, 3*30+3] = [11, 42, 93]
        assert_eq!(output, vec![11, 42, 93]);
    }

    /// Test with empty batch (edge case)
    #[test]
    fn test_jit_empty_batch() {
        let mut jit = JIT::new().unwrap();
        let expr = Expr::add(Expr::ColumnA, Expr::ColumnB);
        
        let col_a: Vec<i64> = vec![];
        let col_b: Vec<i64> = vec![];
        let mut output: Vec<i64> = vec![];
        
        let code_ptr = jit.compile(&expr).unwrap();
        type ComputeFn = extern "C" fn(*const i64, *const i64, *mut i64, usize);
        let compute_fn: ComputeFn = unsafe { mem::transmute(code_ptr) };
        
        compute_fn(col_a.as_ptr(), col_b.as_ptr(), output.as_mut_ptr(), 0);
        
        assert!(output.is_empty());
    }

    /// Test single row batch
    #[test]
    fn test_jit_single_row() {
        let mut jit = JIT::new().unwrap();
        let expr = Expr::mul(Expr::ColumnA, Expr::ColumnB);
        
        let col_a = vec![7i64];
        let col_b = vec![6i64];
        let mut output = vec![0i64; 1];
        
        let code_ptr = jit.compile(&expr).unwrap();
        type ComputeFn = extern "C" fn(*const i64, *const i64, *mut i64, usize);
        let compute_fn: ComputeFn = unsafe { mem::transmute(code_ptr) };
        
        compute_fn(col_a.as_ptr(), col_b.as_ptr(), output.as_mut_ptr(), 1);
        
        assert_eq!(output, vec![42]);
    }
}
