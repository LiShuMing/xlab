// M1.2: Hand-written CUDA C++ fused memory-bound kernels:
//   1. Fused RMSNorm (single-pass row reduction via warp shuffle + shared memory, FP32 accum)
//   2. Online Softmax (Milakov-Gimelshein 2-pass over registers / 1-pass stat merge, no 3rd pass)
//
// Builds standalone binary for correctness self-checks, compute-sanitizer memcheck/racecheck,
// and JSON benchmark output consumed by bench_fused_ops.py.

#include <cuda_bf16.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace {

constexpr int kWarpSize = 32;
constexpr int kMaxWarpsPerBlock = 32;  // Up to 1024 threads per block.

#define CHECK_CUDA(expr)                                                                         \
    do {                                                                                         \
        cudaError_t err__ = (expr);                                                              \
        if (err__ != cudaSuccess) {                                                              \
            std::fprintf(stderr, "CUDA error %s at %s:%d: %s\n", #expr, __FILE__, __LINE__,      \
                         cudaGetErrorString(err__));                                             \
            std::exit(1);                                                                        \
        }                                                                                        \
    } while (0)

__device__ __forceinline__ float WarpReduceSum(float val) {
    for (int offset = kWarpSize / 2; offset > 0; offset >>= 1) {
        val += __shfl_down_sync(0xffffffffu, val, offset);
    }
    return val;
}

struct OnlineSoftmaxState {
    float max_val;
    float sum_exp;
};

__device__ __forceinline__ OnlineSoftmaxState CombineOnlineSoftmax(OnlineSoftmaxState a,
                                                                   OnlineSoftmaxState b) {
    if (a.sum_exp == 0.0f) return b;
    if (b.sum_exp == 0.0f) return a;
    if (a.max_val >= b.max_val) {
        return {a.max_val, a.sum_exp + b.sum_exp * expf(b.max_val - a.max_val)};
    }
    return {b.max_val, b.sum_exp + a.sum_exp * expf(a.max_val - b.max_val)};
}

__device__ __forceinline__ OnlineSoftmaxState WarpReduceOnlineSoftmax(OnlineSoftmaxState state) {
    for (int offset = kWarpSize / 2; offset > 0; offset >>= 1) {
        OnlineSoftmaxState other;
        other.max_val = __shfl_down_sync(0xffffffffu, state.max_val, offset);
        other.sum_exp = __shfl_down_sync(0xffffffffu, state.sum_exp, offset);
        state = CombineOnlineSoftmax(state, other);
    }
    return state;
}

// Fused RMSNorm for FP32 with float4 vectorized path when aligned and divisible by 4.
__global__ void RmsNormFp32Kernel(const float* __restrict__ x, const float* __restrict__ weight,
                                  float* __restrict__ y, int cols, float eps) {
    const int row = blockIdx.x;
    const float* row_x = x + static_cast<size_t>(row) * cols;
    float* row_y = y + static_cast<size_t>(row) * cols;

    float local_sq = 0.0f;
    const bool vec4_ok = ((cols & 3) == 0) &&
                         ((reinterpret_cast<uintptr_t>(row_x) & 15u) == 0) &&
                         ((reinterpret_cast<uintptr_t>(weight) & 15u) == 0) &&
                         ((reinterpret_cast<uintptr_t>(row_y) & 15u) == 0);

    if (vec4_ok) {
        const int vec_cols = cols / 4;
        const float4* x4 = reinterpret_cast<const float4*>(row_x);
        for (int i = threadIdx.x; i < vec_cols; i += blockDim.x) {
            float4 v = x4[i];
            local_sq += v.x * v.x + v.y * v.y + v.z * v.z + v.w * v.w;
        }
    } else {
        for (int i = threadIdx.x; i < cols; i += blockDim.x) {
            float v = row_x[i];
            local_sq += v * v;
        }
    }

    local_sq = WarpReduceSum(local_sq);
    __shared__ float warp_sums[kMaxWarpsPerBlock];
    const int lane = threadIdx.x & (kWarpSize - 1);
    const int warp_id = threadIdx.x / kWarpSize;
    const int num_warps = (blockDim.x + kWarpSize - 1) / kWarpSize;
    if (lane == 0) {
        warp_sums[warp_id] = local_sq;
    }
    __syncthreads();

    if (warp_id == 0) {
        float total_sq = (lane < num_warps) ? warp_sums[lane] : 0.0f;
        total_sq = WarpReduceSum(total_sq);
        if (lane == 0) {
            warp_sums[0] = rsqrtf(total_sq / static_cast<float>(cols) + eps);
        }
    }
    __syncthreads();
    const float inv_rms = warp_sums[0];

    if (vec4_ok) {
        const int vec_cols = cols / 4;
        const float4* x4 = reinterpret_cast<const float4*>(row_x);
        const float4* w4 = reinterpret_cast<const float4*>(weight);
        float4* y4 = reinterpret_cast<float4*>(row_y);
        for (int i = threadIdx.x; i < vec_cols; i += blockDim.x) {
            float4 v = x4[i];
            float4 w = w4[i];
            y4[i] = make_float4(v.x * inv_rms * w.x, v.y * inv_rms * w.y, v.z * inv_rms * w.z,
                                v.w * inv_rms * w.w);
        }
    } else {
        for (int i = threadIdx.x; i < cols; i += blockDim.x) {
            row_y[i] = row_x[i] * inv_rms * weight[i];
        }
    }
}

// Fused RMSNorm for BF16 with FP32 accumulation and __nv_bfloat162 vectorized loads.
__global__ void RmsNormBf16Kernel(const __nv_bfloat16* __restrict__ x,
                                  const __nv_bfloat16* __restrict__ weight,
                                  __nv_bfloat16* __restrict__ y, int cols, float eps) {
    const int row = blockIdx.x;
    const __nv_bfloat16* row_x = x + static_cast<size_t>(row) * cols;
    __nv_bfloat16* row_y = y + static_cast<size_t>(row) * cols;

    float local_sq = 0.0f;
    const bool vec2_ok = ((cols & 1) == 0) &&
                         ((reinterpret_cast<uintptr_t>(row_x) & 3u) == 0) &&
                         ((reinterpret_cast<uintptr_t>(weight) & 3u) == 0) &&
                         ((reinterpret_cast<uintptr_t>(row_y) & 3u) == 0);

    if (vec2_ok) {
        const int vec_cols = cols / 2;
        const __nv_bfloat162* x2 = reinterpret_cast<const __nv_bfloat162*>(row_x);
        for (int i = threadIdx.x; i < vec_cols; i += blockDim.x) {
            float2 v = __bfloat1622float2(x2[i]);
            local_sq += v.x * v.x + v.y * v.y;
        }
    } else {
        for (int i = threadIdx.x; i < cols; i += blockDim.x) {
            float v = __bfloat162float(row_x[i]);
            local_sq += v * v;
        }
    }

    local_sq = WarpReduceSum(local_sq);
    __shared__ float warp_sums[kMaxWarpsPerBlock];
    const int lane = threadIdx.x & (kWarpSize - 1);
    const int warp_id = threadIdx.x / kWarpSize;
    const int num_warps = (blockDim.x + kWarpSize - 1) / kWarpSize;
    if (lane == 0) {
        warp_sums[warp_id] = local_sq;
    }
    __syncthreads();

    if (warp_id == 0) {
        float total_sq = (lane < num_warps) ? warp_sums[lane] : 0.0f;
        total_sq = WarpReduceSum(total_sq);
        if (lane == 0) {
            warp_sums[0] = rsqrtf(total_sq / static_cast<float>(cols) + eps);
        }
    }
    __syncthreads();
    const float inv_rms = warp_sums[0];

    if (vec2_ok) {
        const int vec_cols = cols / 2;
        const __nv_bfloat162* x2 = reinterpret_cast<const __nv_bfloat162*>(row_x);
        const __nv_bfloat162* w2 = reinterpret_cast<const __nv_bfloat162*>(weight);
        __nv_bfloat162* y2 = reinterpret_cast<__nv_bfloat162*>(row_y);
        for (int i = threadIdx.x; i < vec_cols; i += blockDim.x) {
            float2 v = __bfloat1622float2(x2[i]);
            float2 w = __bfloat1622float2(w2[i]);
            y2[i] = __float22bfloat162_rn(make_float2(v.x * inv_rms * w.x, v.y * inv_rms * w.y));
        }
    } else {
        for (int i = threadIdx.x; i < cols; i += blockDim.x) {
            float v = __bfloat162float(row_x[i]);
            float w = __bfloat162float(weight[i]);
            row_y[i] = __float2bfloat16_rn(v * inv_rms * w);
        }
    }
}

// Online Softmax for BF16: computes (max, sum_exp) in a single reduction pass, then writes output.
// Compared to naive 3-pass softmax (max pass + sum_exp pass + normalize pass), cuts 1 full row read.
__global__ void OnlineSoftmaxBf16Kernel(const __nv_bfloat16* __restrict__ x,
                                        __nv_bfloat16* __restrict__ y, int cols) {
    const int row = blockIdx.x;
    const __nv_bfloat16* row_x = x + static_cast<size_t>(row) * cols;
    __nv_bfloat16* row_y = y + static_cast<size_t>(row) * cols;

    OnlineSoftmaxState local{-INFINITY, 0.0f};
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = __bfloat162float(row_x[i]);
        if (v > local.max_val) {
            local.sum_exp = local.sum_exp * expf(local.max_val - v) + 1.0f;
            local.max_val = v;
        } else {
            local.sum_exp += expf(v - local.max_val);
        }
    }

    local = WarpReduceOnlineSoftmax(local);
    __shared__ OnlineSoftmaxState warp_states[kMaxWarpsPerBlock];
    const int lane = threadIdx.x & (kWarpSize - 1);
    const int warp_id = threadIdx.x / kWarpSize;
    const int num_warps = (blockDim.x + kWarpSize - 1) / kWarpSize;
    if (lane == 0) {
        warp_states[warp_id] = local;
    }
    __syncthreads();

    if (warp_id == 0) {
        OnlineSoftmaxState s =
            (lane < num_warps) ? warp_states[lane] : OnlineSoftmaxState{-INFINITY, 0.0f};
        s = WarpReduceOnlineSoftmax(s);
        if (lane == 0) {
            warp_states[0] = s;
        }
    }
    __syncthreads();

    const float row_max = warp_states[0].max_val;
    const float inv_sum = 1.0f / warp_states[0].sum_exp;
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = __bfloat162float(row_x[i]);
        row_y[i] = __float2bfloat16_rn(expf(v - row_max) * inv_sum);
    }
}

int SelectBlockSize(int cols) {
    int threads = 256;
    if (cols <= 128) {
        threads = 128;
    } else if (cols >= 4096) {
        threads = 512;
    }
    return threads;
}

bool RunCorrectnessSuite(bool small_mode) {
    const std::vector<int> test_cols =
        small_mode ? std::vector<int>{127, 513, 1024}
                   : std::vector<int>{127, 256, 513, 1024, 3584, 4096, 8192};
    const int rows = small_mode ? 8 : 32;
    const float eps = 1e-6f;

    for (int cols : test_cols) {
        const size_t n = static_cast<size_t>(rows) * cols;
        std::vector<float> h_x(n), h_w(cols), h_ref_rms(n), h_ref_sm(n);
        for (size_t i = 0; i < n; ++i) {
            float t = std::sin(static_cast<float>(i) * 0.137f + 0.5f) * 12.0f;
            h_x[i] = t;
        }
        for (int c = 0; c < cols; ++c) {
            h_w[c] = 0.8f + 0.4f * std::cos(static_cast<float>(c) * 0.11f);
        }

        for (int r = 0; r < rows; ++r) {
            double sq = 0.0;
            float max_v = -std::numeric_limits<float>::infinity();
            for (int c = 0; c < cols; ++c) {
                float v = h_x[static_cast<size_t>(r) * cols + c];
                sq += static_cast<double>(v) * v;
                if (v > max_v) max_v = v;
            }
            float inv_rms = 1.0f / std::sqrt(static_cast<float>(sq / cols) + eps);
            double sum_exp = 0.0;
            for (int c = 0; c < cols; ++c) {
                size_t idx = static_cast<size_t>(r) * cols + c;
                h_ref_rms[idx] = h_x[idx] * inv_rms * h_w[c];
                sum_exp += std::exp(static_cast<double>(h_x[idx] - max_v));
            }
            for (int c = 0; c < cols; ++c) {
                size_t idx = static_cast<size_t>(r) * cols + c;
                h_ref_sm[idx] =
                    static_cast<float>(std::exp(static_cast<double>(h_x[idx] - max_v)) / sum_exp);
            }
        }

        float *d_x = nullptr, *d_w = nullptr, *d_y = nullptr;
        CHECK_CUDA(cudaMalloc(&d_x, n * sizeof(float)));
        CHECK_CUDA(cudaMalloc(&d_w, cols * sizeof(float)));
        CHECK_CUDA(cudaMalloc(&d_y, n * sizeof(float)));
        CHECK_CUDA(cudaMemcpy(d_x, h_x.data(), n * sizeof(float), cudaMemcpyHostToDevice));
        CHECK_CUDA(cudaMemcpy(d_w, h_w.data(), cols * sizeof(float), cudaMemcpyHostToDevice));
        RmsNormFp32Kernel<<<rows, SelectBlockSize(cols)>>>(d_x, d_w, d_y, cols, eps);
        CHECK_CUDA(cudaGetLastError());
        CHECK_CUDA(cudaDeviceSynchronize());

        std::vector<float> h_out_fp32(n);
        CHECK_CUDA(cudaMemcpy(h_out_fp32.data(), d_y, n * sizeof(float), cudaMemcpyDeviceToHost));
        float max_err_fp32 = 0.0f;
        for (size_t i = 0; i < n; ++i) {
            max_err_fp32 = std::max(max_err_fp32, std::fabs(h_out_fp32[i] - h_ref_rms[i]));
        }
        CHECK_CUDA(cudaFree(d_x));
        CHECK_CUDA(cudaFree(d_w));
        CHECK_CUDA(cudaFree(d_y));

        if (max_err_fp32 > 1e-4f) {
            std::fprintf(stderr, "FAIL RmsNormFp32 cols=%d max_err=%g\n", cols, max_err_fp32);
            return false;
        }

        std::vector<__nv_bfloat16> h_x_bf16(n), h_w_bf16(cols), h_out_bf16(n);
        for (size_t i = 0; i < n; ++i) h_x_bf16[i] = __float2bfloat16_rn(h_x[i]);
        for (int c = 0; c < cols; ++c) h_w_bf16[c] = __float2bfloat16_rn(h_w[c]);

        __nv_bfloat16 *d_xb = nullptr, *d_wb = nullptr, *d_yb = nullptr;
        CHECK_CUDA(cudaMalloc(&d_xb, n * sizeof(__nv_bfloat16)));
        CHECK_CUDA(cudaMalloc(&d_wb, cols * sizeof(__nv_bfloat16)));
        CHECK_CUDA(cudaMalloc(&d_yb, n * sizeof(__nv_bfloat16)));
        CHECK_CUDA(
            cudaMemcpy(d_xb, h_x_bf16.data(), n * sizeof(__nv_bfloat16), cudaMemcpyHostToDevice));
        CHECK_CUDA(
            cudaMemcpy(d_wb, h_w_bf16.data(), cols * sizeof(__nv_bfloat16), cudaMemcpyHostToDevice));

        RmsNormBf16Kernel<<<rows, SelectBlockSize(cols)>>>(d_xb, d_wb, d_yb, cols, eps);
        CHECK_CUDA(cudaGetLastError());
        CHECK_CUDA(cudaDeviceSynchronize());
        CHECK_CUDA(
            cudaMemcpy(h_out_bf16.data(), d_yb, n * sizeof(__nv_bfloat16), cudaMemcpyDeviceToHost));
        float max_err_bf16_rms = 0.0f;
        for (size_t i = 0; i < n; ++i) {
            max_err_bf16_rms =
                std::max(max_err_bf16_rms, std::fabs(__bfloat162float(h_out_bf16[i]) - h_ref_rms[i]));
        }

        OnlineSoftmaxBf16Kernel<<<rows, SelectBlockSize(cols)>>>(d_xb, d_yb, cols);
        CHECK_CUDA(cudaGetLastError());
        CHECK_CUDA(cudaDeviceSynchronize());
        CHECK_CUDA(
            cudaMemcpy(h_out_bf16.data(), d_yb, n * sizeof(__nv_bfloat16), cudaMemcpyDeviceToHost));
        float max_err_bf16_sm = 0.0f;
        float max_row_sum_err = 0.0f;
        for (int r = 0; r < rows; ++r) {
            float row_sum = 0.0f;
            for (int c = 0; c < cols; ++c) {
                size_t idx = static_cast<size_t>(r) * cols + c;
                float got = __bfloat162float(h_out_bf16[idx]);
                row_sum += got;
                max_err_bf16_sm = std::max(max_err_bf16_sm, std::fabs(got - h_ref_sm[idx]));
            }
            max_row_sum_err = std::max(max_row_sum_err, std::fabs(row_sum - 1.0f));
        }

        CHECK_CUDA(cudaFree(d_xb));
        CHECK_CUDA(cudaFree(d_wb));
        CHECK_CUDA(cudaFree(d_yb));

        if (max_err_bf16_rms > 3e-2f || max_err_bf16_sm > 2e-2f || max_row_sum_err > 2e-2f) {
            std::fprintf(stderr,
                         "FAIL BF16 cols=%d rms_err=%g sm_err=%g row_sum_err=%g\n",
                         cols, max_err_bf16_rms, max_err_bf16_sm, max_row_sum_err);
            return false;
        }
        std::printf("PASS cols=%-5d fp32_rms_err=%.2e bf16_rms_err=%.2e bf16_sm_err=%.2e\n",
                    cols, max_err_fp32, max_err_bf16_rms, max_err_bf16_sm);
    }
    return true;
}

void RunBench(const std::string& op, int rows, int cols, int warmup, int iters) {
    const size_t n = static_cast<size_t>(rows) * cols;
    std::vector<__nv_bfloat16> h_x(n), h_w(cols);
    for (size_t i = 0; i < n; ++i) {
        h_x[i] = __float2bfloat16_rn(std::sin(static_cast<float>(i % 1024) * 0.01f));
    }
    for (int c = 0; c < cols; ++c) {
        h_w[c] = __float2bfloat16_rn(1.0f);
    }

    __nv_bfloat16 *d_x = nullptr, *d_w = nullptr, *d_y = nullptr;
    int32_t* d_flush = nullptr;
    const size_t flush_bytes = 64ull * 1024 * 1024;
    CHECK_CUDA(cudaMalloc(&d_x, n * sizeof(__nv_bfloat16)));
    CHECK_CUDA(cudaMalloc(&d_w, cols * sizeof(__nv_bfloat16)));
    CHECK_CUDA(cudaMalloc(&d_y, n * sizeof(__nv_bfloat16)));
    CHECK_CUDA(cudaMalloc(&d_flush, flush_bytes));
    CHECK_CUDA(cudaMemcpy(d_x, h_x.data(), n * sizeof(__nv_bfloat16), cudaMemcpyHostToDevice));
    CHECK_CUDA(cudaMemcpy(d_w, h_w.data(), cols * sizeof(__nv_bfloat16), cudaMemcpyHostToDevice));

    const int threads = SelectBlockSize(cols);
    auto launch = [&]() {
        if (op == "rmsnorm") {
            RmsNormBf16Kernel<<<rows, threads>>>(d_x, d_w, d_y, cols, 1e-6f);
        } else {
            OnlineSoftmaxBf16Kernel<<<rows, threads>>>(d_x, d_y, cols);
        }
    };

    for (int i = 0; i < warmup; ++i) launch();
    CHECK_CUDA(cudaDeviceSynchronize());

    std::vector<cudaEvent_t> starts(iters), ends(iters);
    for (int i = 0; i < iters; ++i) {
        CHECK_CUDA(cudaEventCreate(&starts[i]));
        CHECK_CUDA(cudaEventCreate(&ends[i]));
        CHECK_CUDA(cudaMemsetAsync(d_flush, 0, flush_bytes));
        CHECK_CUDA(cudaEventRecord(starts[i]));
        launch();
        CHECK_CUDA(cudaEventRecord(ends[i]));
    }
    CHECK_CUDA(cudaDeviceSynchronize());

    std::vector<float> times(iters);
    for (int i = 0; i < iters; ++i) {
        CHECK_CUDA(cudaEventElapsedTime(&times[i], starts[i], ends[i]));
        CHECK_CUDA(cudaEventDestroy(starts[i]));
        CHECK_CUDA(cudaEventDestroy(ends[i]));
    }
    std::sort(times.begin(), times.end());
    const float median_ms = times[iters / 2];
    const size_t bytes_moved =
        (op == "rmsnorm") ? (2 * n + cols) * sizeof(__nv_bfloat16) : (2 * n) * sizeof(__nv_bfloat16);
    const double bw_gb_s = static_cast<double>(bytes_moved) / (median_ms * 1e-3) / 1e9;

    std::printf(
        "{\"op\":\"%s\",\"rows\":%d,\"cols\":%d,\"median_ms\":%.5f,\"bw_gb_s\":%.1f}\n",
        op.c_str(), rows, cols, median_ms, bw_gb_s);

    CHECK_CUDA(cudaFree(d_x));
    CHECK_CUDA(cudaFree(d_w));
    CHECK_CUDA(cudaFree(d_y));
    CHECK_CUDA(cudaFree(d_flush));
}

}  // namespace

int main(int argc, char** argv) {
    bool do_test = false;
    bool small_mode = false;
    std::string bench_op;
    int rows = 4096;
    int cols = 4096;
    int warmup = 10;
    int iters = 50;

    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--test") == 0) {
            do_test = true;
        } else if (std::strcmp(argv[i], "--small") == 0) {
            small_mode = true;
        } else if (std::strcmp(argv[i], "--bench") == 0 && i + 1 < argc) {
            bench_op = argv[++i];
        } else if (std::strcmp(argv[i], "--rows") == 0 && i + 1 < argc) {
            rows = std::atoi(argv[++i]);
        } else if (std::strcmp(argv[i], "--cols") == 0 && i + 1 < argc) {
            cols = std::atoi(argv[++i]);
        } else if (std::strcmp(argv[i], "--iters") == 0 && i + 1 < argc) {
            iters = std::atoi(argv[++i]);
        }
    }

    if (do_test || bench_op.empty()) {
        if (!RunCorrectnessSuite(small_mode)) {
            return 1;
        }
    }
    if (!bench_op.empty()) {
        RunBench(bench_op, rows, cols, warmup, iters);
    }
    return 0;
}
