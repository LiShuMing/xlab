"""M1.2: Hand-written Triton kernels for Fused RMSNorm and Fused Online Softmax.

Both kernels accumulate in FP32 and load each row once into on-chip SRAM (registers/shared
memory) when cols <= MAX_FUSED_SIZE, avoiding intermediate global-memory round-trips.
"""

from __future__ import annotations

import torch
import triton
import triton.language as tl


@triton.jit
def _rmsnorm_fwd_kernel(
    x_ptr,
    w_ptr,
    y_ptr,
    stride_x_row,
    stride_y_row,
    n_cols,
    eps,
    BLOCK_SIZE: tl.constexpr,
):
    row_idx = tl.program_id(0)
    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < n_cols

    x_row_ptr = x_ptr + row_idx * stride_x_row + col_offs
    y_row_ptr = y_ptr + row_idx * stride_y_row + col_offs

    x = tl.load(x_row_ptr, mask=mask, other=0.0).to(tl.float32)
    w = tl.load(w_ptr + col_offs, mask=mask, other=0.0).to(tl.float32)

    mean_sq = tl.sum(x * x, axis=0) / n_cols
    inv_rms = tl.rsqrt(mean_sq + eps)
    y = x * inv_rms * w
    tl.store(y_row_ptr, y.to(y_ptr.dtype.element_ty), mask=mask)


@triton.jit
def _softmax_fwd_kernel(
    x_ptr,
    y_ptr,
    stride_x_row,
    stride_y_row,
    n_cols,
    BLOCK_SIZE: tl.constexpr,
):
    row_idx = tl.program_id(0)
    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < n_cols

    x_row_ptr = x_ptr + row_idx * stride_x_row + col_offs
    y_row_ptr = y_ptr + row_idx * stride_y_row + col_offs

    x = tl.load(x_row_ptr, mask=mask, other=-float("inf")).to(tl.float32)
    x_shifted = x - tl.max(x, axis=0)
    numerator = tl.exp(x_shifted)
    denominator = tl.sum(numerator, axis=0)
    y = numerator / denominator
    tl.store(y_row_ptr, y.to(y_ptr.dtype.element_ty), mask=mask)


def triton_rmsnorm(x: torch.Tensor, weight: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Single-pass fused RMSNorm over the last dimension."""
    assert x.is_cuda and weight.is_cuda, "Inputs must reside on CUDA."
    assert x.ndim == 2 and weight.ndim == 1 and x.shape[1] == weight.shape[0]
    n_rows, n_cols = x.shape
    block_size = triton.next_power_of_2(n_cols)
    if block_size > 65536:
        raise ValueError(f"Unsupported n_cols={n_cols} for single-block fused RMSNorm.")
    num_warps = 4 if block_size <= 2048 else (8 if block_size <= 8192 else 16)
    y = torch.empty_like(x)
    _rmsnorm_fwd_kernel[(n_rows,)](
        x,
        weight,
        y,
        x.stride(0),
        y.stride(0),
        n_cols,
        eps,
        BLOCK_SIZE=block_size,
        num_warps=num_warps,
    )
    return y


def triton_softmax(x: torch.Tensor) -> torch.Tensor:
    """Single-pass fused Softmax over the last dimension."""
    assert x.is_cuda and x.ndim == 2, "Input must be a 2D CUDA tensor."
    n_rows, n_cols = x.shape
    block_size = triton.next_power_of_2(n_cols)
    if block_size > 65536:
        raise ValueError(f"Unsupported n_cols={n_cols} for single-block fused Softmax.")
    num_warps = 4 if block_size <= 2048 else (8 if block_size <= 8192 else 16)
    y = torch.empty_like(x)
    _softmax_fwd_kernel[(n_rows,)](
        x,
        y,
        x.stride(0),
        y.stride(0),
        n_cols,
        BLOCK_SIZE=block_size,
        num_warps=num_warps,
    )
    return y
