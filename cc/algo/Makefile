CXX = g++
CXXFLAGS = -std=c++17 -O0 -fno-omit-frame-pointer -g
# CXXFLAGS = -std=c++17 -O2

# Get the directory where this Makefile is located
# This allows the Makefile to work when called with -f from subdirectories
MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
MAKEFILE_DIR := $(dir $(MAKEFILE_PATH))

# Determine if we're running from the Makefile's directory or from a subdirectory
# If Makefile is in current directory, use simple relative paths
# Otherwise, use paths relative to the Makefile location
CURRENT_DIR := $(abspath .)
ifeq ($(MAKEFILE_DIR),$(CURRENT_DIR)/)
    # Running from Makefile's directory
    BIN_DIR = bin
    SRC_LEETCODE_DIR = src/leetcode
	SRC_HACKERRANK_DIR = src/hackerrank
    SRC_ALGO_DIR = src/algo
    SRC_LCR_DIR = src/lcr
    SRC_DAILYPROGRAMMER_DIR = src/dailyprogrammer
    SRC_MSJD_DIR = src/msjd
    SRC_LINUX_DIR = src/linux
else
    # Running from subdirectory with -f flag, use paths relative to Makefile
    BIN_DIR = $(MAKEFILE_DIR)bin
    SRC_LEETCODE_DIR = $(MAKEFILE_DIR)src/leetcode
    SRC_HACKERRANK_DIR = $(MAKEFILE_DIR)src/hackerrank
    SRC_ALGO_DIR = $(MAKEFILE_DIR)src/algo
    SRC_LCR_DIR = $(MAKEFILE_DIR)src/lcr
    SRC_DAILYPROGRAMMER_DIR = $(MAKEFILE_DIR)src/dailyprogrammer
    SRC_MSJD_DIR = $(MAKEFILE_DIR)src/msjd
    SRC_LINUX_DIR = $(MAKEFILE_DIR)src/linux
endif

# Pattern rule for leetcode files - automatically builds any leetcode_*.cc file
leetcode_%: $(SRC_LEETCODE_DIR)/leetcode_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

# Pattern rule for LCR files
lcr_%: $(SRC_LCR_DIR)/lcr_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

hackerrank_%: $(SRC_HACKERRANK_DIR)/hackerrank_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

# Pattern rule for algo files - only build specified file if needed
algo_%: $(SRC_ALGO_DIR)/algo_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

concurrent_%: $(SRC_ALGO_DIR)/concurrent/concurrent_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

dp_%: $(SRC_DAILYPROGRAMMER_DIR)/dp_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

jd_%: $(SRC_MSJD_DIR)/jd_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

l_%: $(SRC_LINUX_DIR)/l_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

# Run targets: build then execute (e.g. make run_leetcode_1102 [ARGS="..."])
run_leetcode_%: leetcode_%
	$(BIN_DIR)/leetcode_$* $(ARGS)

run_lcr_%: lcr_%
	$(BIN_DIR)/lcr_$* $(ARGS)

run_hackerrank_%: hackerrank_%
	$(BIN_DIR)/hackerrank_$* $(ARGS)

run_algo_%: algo_%
	$(BIN_DIR)/algo_$* $(ARGS)

run_concurrent_%: concurrent_%
	$(BIN_DIR)/concurrent_$* $(ARGS)

run_dp_%: dp_%
	$(BIN_DIR)/dp_$* $(ARGS)

run_jd_%: jd_%
	$(BIN_DIR)/jd_$* $(ARGS)

run_l_%: l_%
	$(BIN_DIR)/l_$* $(ARGS)

# Test: build a few targets to verify toolchain and Makefile in this env
test: leetcode_1102 lcr_161
	@echo "test: build ok"

# Convenience target to build all algorithms
algo_all: $(patsubst $(SRC_ALGO_DIR)/algo_%.cc,algo_%, $(wildcard $(SRC_ALGO_DIR)/algo_*.cc))

$(BIN_DIR)/%: $(SRC_ALGO_DIR)/%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $<

clean:
	rm -f $(BIN_DIR)/*

# Help target
help:
	@echo "Available targets:"
	@echo "  leetcode_<n>       - Build (e.g., make leetcode_1102)"
	@echo "  lcr_<n>            - Build (e.g., make lcr_159)"
	@echo "  run_leetcode_<n>   - Build and run (e.g., make run_leetcode_1102 [ARGS='...'])"
	@echo "  run_lcr_<n>        - Build and run (e.g., make run_lcr_161)"
	@echo "  run_algo_<name>    - Build and run algo (run_jd_*, run_dp_*, run_l_*, etc.)"
	@echo "  test               - Build a few targets to verify env"
	@echo "  clean              - Remove all binaries"
	@echo ""
	@echo "Usage:"
	@echo "  make leetcode_1102"
	@echo "  make run_leetcode_1102"
	@echo "  make run_leetcode_1102 ARGS='arg1 arg2'"
	@echo "  make test"
	@echo "  make -f ../Makefile run_leetcode_1102   # from subdir"
