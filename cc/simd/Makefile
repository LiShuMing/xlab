CXX ?= g++
AVX ?= -mavx2
AVX512 ?= -mavx512f
CXXFLAGS ?= -std=c++20 -O3 -march=native $(AVX) $(AVX512)

SRC_DIR := src
BIN_DIR := bin
SIMD_DIR := $(SRC_DIR)/simd
TEST_DIR := $(SRC_DIR)/test

# Ensure the binary directory exists before building targets
$(BIN_DIR):
	@mkdir -p $@

# Find all .cpp files in each relevant directory and compile them to BIN_DIR with pattern rule
SIMD_SRCS := $(wildcard $(SIMD_DIR)/*.cpp)
TEST_SRCS := $(wildcard $(TEST_DIR)/*.cpp)

SIMD_SRCS := $(wildcard $(SIMD_DIR)/*.cpp)
TEST_SRCS := $(wildcard $(TEST_DIR)/*.cpp)

SIMD_BINS := $(patsubst $(SIMD_DIR)/%.cpp,$(BIN_DIR)/%,$(SIMD_SRCS))
TEST_BINS := $(patsubst $(TEST_DIR)/%.cpp,$(BIN_DIR)/%,$(TEST_SRCS))

# Pattern rules for compiling any .cpp file from simd or test dir to bin/
$(BIN_DIR)/%: $(SIMD_DIR)/%.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

$(BIN_DIR)/%: $(TEST_DIR)/%.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< -o $@

# 'all' builds every binary for files in simd and test dirs
all: $(SIMD_BINS) $(TEST_BINS)

# Per-file targets for anything in simd directory (auto-generated)
$(foreach src,$(SIMD_SRCS),$(eval $(basename $(notdir $(src))): $(BIN_DIR)/$(basename $(notdir $(src)))))

# Per-file targets for anything in test directory (auto-generated)
$(foreach src,$(TEST_SRCS),$(eval $(basename $(notdir $(src))): $(BIN_DIR)/$(basename $(notdir $(src)))))


.PHONY: clean
clean:
	@rm -f $(BIN_DIR)/*