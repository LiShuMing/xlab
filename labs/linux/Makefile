# Linux 机制学习 lab 的统一构建入口。
# pagetable 是 C 风格代码但按 C++ 编译；rcu 依赖 pthread，用 C 编译。

CXX ?= g++
CC ?= gcc
CXXFLAGS ?= -std=c++17 -O0 -fno-omit-frame-pointer -g
CFLAGS ?= -O2 -Wall -Wextra -pthread
BIN_DIR := bin

PAGETABLE_SRCS := $(wildcard pagetable/l_*.cc)
PAGETABLE_BINS := $(patsubst pagetable/%.cc,$(BIN_DIR)/%,$(PAGETABLE_SRCS))
RCU_BIN := $(BIN_DIR)/rcu_lab

.PHONY: all pagetable rcu run_rcu clean

all: pagetable rcu

pagetable: $(PAGETABLE_BINS)

rcu: $(RCU_BIN)

$(BIN_DIR)/%: pagetable/%.cc | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

$(RCU_BIN): rcu/rcu_lab.c | $(BIN_DIR)
	$(CC) $(CFLAGS) $< -o $@

run_rcu: $(RCU_BIN)
	$(RCU_BIN)

$(BIN_DIR):
	mkdir -p $@

clean:
	rm -rf $(BIN_DIR)
