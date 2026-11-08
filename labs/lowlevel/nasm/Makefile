# NASM 汇编教程的构建入口。三类目标链接方式不同：
#   _start 程序：nasm 出 .o 后用 ld 直接链接，不依赖 libc
#   libc 程序：nasm 出 .o 后用 gcc 链接，用到 printf / atoi / puts
#   库函数（square、mywrite）：只出 .o，再由 C 驱动 demo 链接
# 只支持 Linux x86_64；*_macos / *_mac 是 ARM64 Darwin 版本，仅作对照保留。

NASM ?= nasm
CC ?= gcc
LD ?= ld
BUILD_DIR := bin
TUTORIAL_DIR := src/tutorial
HELLO_DIR := src/hello

ifeq ($(shell command -v $(NASM) >/dev/null 2>&1 && echo ok),)
$(error 找不到 NASM 汇编器（$(NASM)）。安装：conda create -y -n asm nasm 后 conda activate asm；或 make NASM=/path/to/nasm)
endif

# 目标对应的源文件：tutorial/<name>_linux.asm 优先，其次 tutorial/<name>.asm，最后 hello/<name>.asm。
src_for = $(firstword $(wildcard $(TUTORIAL_DIR)/$(1)_linux.asm) $(wildcard $(TUTORIAL_DIR)/$(1).asm) $(wildcard $(HELLO_DIR)/$(1).asm))

STANDALONE := t1 t2 t3 t5 t6 hello hello2
LIBC_PROGRAMS := average fib power
LIBRARY_OBJECTS := square mywrite

STANDALONE_BINS := $(addprefix $(BUILD_DIR)/,$(STANDALONE))
LIBC_BINS := $(addprefix $(BUILD_DIR)/,$(LIBC_PROGRAMS))
LIB_OBJS := $(addprefix $(BUILD_DIR)/,$(addsuffix .o,$(LIBRARY_OBJECTS)))
DEMO_BIN := $(BUILD_DIR)/demo

.PHONY: all help run-% clean

all: $(STANDALONE_BINS) $(LIBC_BINS) $(LIB_OBJS) $(DEMO_BIN)

help:
	@echo "make all            构建全部目标"
	@echo "make run-<name>     构建并运行单个目标，例如 make run-t1；ARGS 透传参数"
	@echo "make clean          删除 $(BUILD_DIR)/"
	@echo ""
	@echo "_start 程序: $(STANDALONE)"
	@echo "libc 程序:   $(LIBC_PROGRAMS)"
	@echo "库函数:      $(LIBRARY_OBJECTS)（另加 demo 驱动）"

$(BUILD_DIR):
	@mkdir -p $@

$(BUILD_DIR)/%.o: | $(BUILD_DIR)
	$(NASM) -f elf64 -o $@ $(call src_for,$*)

$(STANDALONE_BINS): $(BUILD_DIR)/%: $(BUILD_DIR)/%.o
	$(LD) -o $@ $<

# -no-pie：教程代码用绝对地址寻址，PIE 链接会报 R_X86_64_32S 重定位错误。
$(LIBC_BINS): $(BUILD_DIR)/%: $(BUILD_DIR)/%.o
	$(CC) -no-pie -o $@ $<

$(DEMO_BIN): $(TUTORIAL_DIR)/main.c $(LIB_OBJS)
	$(CC) -no-pie -o $@ $^

run-%: $(BUILD_DIR)/%
	@./$< $(ARGS)

clean:
	@rm -rf $(BUILD_DIR)
