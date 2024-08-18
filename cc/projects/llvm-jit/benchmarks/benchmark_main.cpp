#include <benchmark/benchmark.h>

#include <memory>
#include <vector>

#include "M1_AST.h"
#include "Utils.h"

using namespace llvm_jit;

static void BM_ConstExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::cst(42.0);
    std::vector<double> input;
    for (auto _ : state) {
        volatile auto result = expr->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_ConstExpr);

static void BM_VarExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::var(0);
    std::vector<double> input = {3.14};
    for (auto _ : state) {
        volatile auto result = expr->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_VarExpr);

static void BM_AddExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::cst(5.0));
    std::vector<double> input = {2.0};
    for (auto _ : state) {
        volatile auto result = expr->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_AddExpr);

static void BM_MulExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(3.0));
    std::vector<double> input = {7.0};
    for (auto _ : state) {
        volatile auto result = expr->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_MulExpr);

static void BM_ComplexExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(2.0)),
            ExpressionBuilder::var(1));
    std::vector<double> input = {3.0, 5.0};
    for (auto _ : state) {
        volatile auto result = expr->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_ComplexExpr);

static void BM_NestedExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::add(
                    ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::cst(1.0)),
                    ExpressionBuilder::cst(2.0)),
            ExpressionBuilder::cst(3.0));
    std::vector<double> input = {10.0};
    for (auto _ : state) {
        volatile auto result = expr->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_NestedExpr);

static void BM_CloneExpr(benchmark::State& state) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(2.0)),
            ExpressionBuilder::cst(1.0));
    std::vector<double> input = {5.0};
    for (auto _ : state) {
        auto cloned = expr->clone();
        volatile auto result = cloned->eval(input);
        (void)result;
    }
}
BENCHMARK(BM_CloneExpr);

static void BM_ToString(benchmark::State& state) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(2.0)),
            ExpressionBuilder::var(1));
    for (auto _ : state) {
        volatile auto str = expr->toString();
        (void)str;
    }
}
BENCHMARK(BM_ToString);

BENCHMARK_MAIN();
