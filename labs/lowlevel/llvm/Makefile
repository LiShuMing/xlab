# LLVM（Low Level Virtual Machine）IR（Intermediate Representation，中间表示）实验的
# 构建入口：手写 IR、clang 生成的三档 IR、自写 pass 插件，产物统一落 bin/。
LLVM_CONFIG ?= llvm-config
CLANG ?= clang
LLVM_AS ?= llvm-as
# 插件必须与 LLVM 共用一套 libstdc++ ABI：本机系统 g++ 固定带
# -D_GLIBCXX_USE_CXX11_ABI=0（旧 ABI），编出的 .so 加载进 opt 会因 std::string
# 布局不同而崩溃，所以用 conda 环境里与 LLVM 18 同源的工具链。
CXX ?= x86_64-conda-linux-gnu-g++

ifeq ($(shell command -v $(LLVM_CONFIG) >/dev/null 2>&1 && echo ok),)
$(error 找不到 llvm-config。装 LLVM 18：conda create -y -n llvm18 -c conda-forge --override-channels llvm=18 clang=18 llvmdev=18 clangxx gxx_linux-64 然后 conda activate llvm18)
endif

# lli / opt / clang / 编译器统一取自 llvm-config 所在的安装，避免混用系统里的旧工具。
export PATH := $(shell $(LLVM_CONFIG) --bindir):$(PATH)

BIN := bin
IR_DIR := src/ir
CPP_DIR := src/cpp
PASS_DIR := src/pass
CLANG_OUT := $(BIN)/clang
PASS_OUT := $(BIN)/passes

HAND_LL := $(wildcard $(IR_DIR)/*.ll)
HAND_BC := $(patsubst $(IR_DIR)/%.ll,$(BIN)/%.bc,$(HAND_LL))

CPP_SRC := $(wildcard $(CPP_DIR)/*.cpp)
CPP_OUT := $(foreach level,O0 O2 O3,$(patsubst $(CPP_DIR)/%.cpp,$(CLANG_OUT)/%-$(level).ll,$(CPP_SRC)))

PASS_NAMES := IrStats MulToShift
PASS_SO := $(patsubst %,$(PASS_OUT)/%.so,$(PASS_NAMES))

# llvm-config 的 cxxflags 已含 -std=c++17 与 LLVM 需要的宏；不要再加 -fno-rtti，
# conda 的 LLVM 是带 RTTI 构建的。也不要加 -Wextra：LLVM 头文件在 -Wextra 下会刷出
# 大量 unused-parameter 警告，把真正有用的输出淹没。
PASS_CXXFLAGS := $(shell $(LLVM_CONFIG) --cxxflags) -fPIC -Wall

.PHONY: all ir clang-ir plugin check passes help clean

all: ir clang-ir plugin

# 手写 IR 只需过 llvm-as：能汇编成 .bc 就说明语法与类型合法。
ir: $(HAND_BC)

$(BIN)/%.bc: $(IR_DIR)/%.ll
	@mkdir -p $(BIN)
	$(LLVM_AS) -o $@ $<

clang-ir: $(CPP_OUT)

# -O0 的产物默认给每个函数加 optnone 属性，任何 pass 都会跳过它，IR 就成了一块
# 动不了的石头。加 -Xclang -disable-O0-optnone 才能把 -O0 IR 当作 pass 的输入，
# 这是 LLVM 教学里的标准做法。
$(CLANG_OUT)/%-O0.ll: $(CPP_DIR)/%.cpp
	@mkdir -p $(CLANG_OUT)
	$(CLANG) -O0 -Xclang -disable-O0-optnone -S -emit-llvm $< -o $@

$(CLANG_OUT)/%-O2.ll: $(CPP_DIR)/%.cpp
	@mkdir -p $(CLANG_OUT)
	$(CLANG) -O2 -S -emit-llvm $< -o $@

$(CLANG_OUT)/%-O3.ll: $(CPP_DIR)/%.cpp
	@mkdir -p $(CLANG_OUT)
	$(CLANG) -O3 -S -emit-llvm $< -o $@

plugin: $(PASS_SO)

# 只编 .so，不链 libLLVM：插件里的 LLVM 符号由加载它的 opt 提供。
$(PASS_OUT)/%.so: $(PASS_DIR)/%.cpp
	@mkdir -p $(PASS_OUT)
	$(CXX) $(PASS_CXXFLAGS) -shared -o $@ $<

check: all
	@scripts/check.sh

passes: all
	@scripts/pass-diff.sh $(CLANG_OUT)/loop_sum-O0.ll mem2reg
	@scripts/pass-diff.sh $(IR_DIR)/04_loop_invariant.ll 'loop-mssa(licm)'
	@scripts/pass-diff.sh $(IR_DIR)/01_basics.ll instcombine

help:
	@echo "make            构建全部：IR 语法校验 + clang 三档 IR + 两个插件"
	@echo "make ir         只做手写 IR 的语法校验（llvm-as 汇编成 bin/*.bc）"
	@echo "make clang-ir   用 clang 生成 -O0/-O2/-O3 三档 IR 到 bin/clang/"
	@echo "make plugin     编译自写 pass 插件到 bin/passes/"
	@echo "make check      断言：lli 执行结果、opt verify、自写 pass 生效"
	@echo "make passes     逐 pass 打印指令行数与 before/after diff"
	@echo "make clean      删除 bin/"

clean:
	@rm -rf $(BIN)
