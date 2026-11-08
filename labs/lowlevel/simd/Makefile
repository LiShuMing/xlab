# SIMD 实验的构建入口：src/simd/*.cpp 各自带 main，独立编译成 bin/<name>。
CXX ?= g++
# 源码只用 C++17 特性。GCC 9 不认 -std=c++20，故固定在 C++17，避免构建环境差异。
STD ?= -std=c++17
# 本机需要 AVX2（test_simd.cpp 直接调用 _mm256_* 内建函数）；换机器先看
# /proc/cpuinfo 的 flags，缺 avx2 时用 make AVX= 覆盖。
AVX ?= -mavx2
CXXFLAGS ?= $(STD) -O3 -march=native $(AVX)

SRC_DIR := src/simd
BIN_DIR := bin
SRCS := $(wildcard $(SRC_DIR)/*.cpp)
BINS := $(patsubst $(SRC_DIR)/%.cpp,$(BIN_DIR)/%,$(SRCS))

.PHONY: all run-% clean

all: $(BINS)

$(BIN_DIR):
	@mkdir -p $@

$(BIN_DIR)/%: $(SRC_DIR)/%.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

# make run-<name>，例如 make run-simd1；ARGS 透传命令行参数。
run-%: $(BIN_DIR)/%
	@./$< $(ARGS)

clean:
	@rm -rf $(BIN_DIR)
