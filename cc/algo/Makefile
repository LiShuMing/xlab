CXX = g++
# CXXFLAGS = -std=c++17 -O0 -fno-omit-frame-pointer -g
CXXFLAGS = -std=c++17 -O2

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
    SRC_ALGO_DIR = src/algo
    SRC_LCR_DIR = src/lcr
else
    # Running from subdirectory with -f flag, use paths relative to Makefile
    BIN_DIR = $(MAKEFILE_DIR)bin
    SRC_LEETCODE_DIR = $(MAKEFILE_DIR)src/leetcode
    SRC_ALGO_DIR = $(MAKEFILE_DIR)src/algo
    SRC_LCR_DIR = $(MAKEFILE_DIR)src/lcr
endif

# Pattern rule for leetcode files - automatically builds any leetcode_*.cc file
leetcode_%: $(SRC_LEETCODE_DIR)/leetcode_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

# Pattern rule for LCR files
lcr_%: $(SRC_LCR_DIR)/lcr_%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $(BIN_DIR)/$@ $<

# Automatically generate a binary for each .cc file in src/algo directory
ALGO_SRCS := $(wildcard $(SRC_ALGO_DIR)/*.cc)
ALGO_BINS := $(patsubst $(SRC_ALGO_DIR)/%.cc, $(BIN_DIR)/%, $(ALGO_SRCS))

algo_all: $(ALGO_BINS)

$(BIN_DIR)/%: $(SRC_ALGO_DIR)/%.cc
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $<


clean:
	rm -f $(BIN_DIR)/*

# Help target
help:
	@echo "Available targets:"
	@echo "  leetcode_<number>  - Build a leetcode solution (e.g., make leetcode_1102)"
	@echo "  lcr_<number>       - Build an LCR solution (e.g., make lcr_159)"
	@echo "  topo_sort          - Build topological sort example"
	@echo "  clean              - Remove all binaries"
	@echo ""
	@echo "Usage:"
	@echo "  From algo directory:  make leetcode_1102"
	@echo "  From subdirectories:  make -f ../../Makefile leetcode_1102"
