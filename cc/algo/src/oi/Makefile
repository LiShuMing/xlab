CXX ?= c++
CPPFLAGS ?=
CXXFLAGS ?= -std=c++17 -O0 -g -Wall -Wextra -Wpedantic
LDFLAGS ?=

# 所有二进制留在已有忽略规则覆盖的 bin/ 下，不写入源码目录。
BIN_DIR := ../../bin
DEMO := $(BIN_DIR)/oi_segment_tree_rollback_dsu
TEST := $(BIN_DIR)/oi_segment_tree_rollback_dsu_test
HEADERS := offline_dynamic_connectivity.h ../include/fwd.h

.PHONY: all demo test
all: $(DEMO) $(TEST)

$(BIN_DIR):
	mkdir -p $@

$(DEMO): oi_segment_tree_rollback_dsu.cc $(HEADERS) | $(BIN_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@ $(LDFLAGS)

$(TEST): oi_segment_tree_rollback_dsu_test.cc $(HEADERS) | $(BIN_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@ $(LDFLAGS)

demo: $(DEMO)
	$(DEMO)

test: $(TEST)
	$(TEST)
