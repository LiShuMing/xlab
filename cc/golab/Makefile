# Makefile for golab leetcode solutions

GO := go
MODULE := cc/golab
SRC_DIR := src/leetcode
OUTPUT_DIR := bin

# Find all leetcode_*.go files
LEETCODE_FILES := $(wildcard $(SRC_DIR)/leetcode_*.go)
LEETCODE_BINS := $(patsubst $(SRC_DIR)/leetcode_%.go,$(OUTPUT_DIR)/leetcode_%,$(LEETCODE_FILES))

# Default target: build all leetcode binaries
.PHONY: all
all: $(LEETCODE_BINS)

# Pattern rule to build individual leetcode problems
$(OUTPUT_DIR)/leetcode_%: $(SRC_DIR)/leetcode_%.go
	@mkdir -p $(OUTPUT_DIR)
	$(GO) build -o $@ $<

# Run a specific problem
# Example: make leetcode_433

leetcode_%: $(OUTPUT_DIR)/leetcode_%
	./$(OUTPUT_DIR)/$@

# Clean build artifacts
.PHONY: clean
clean:
	rm -rf $(OUTPUT_DIR)

# List all available problems
.PHONY: list
list:
	@echo "Available LeetCode problems:"
	@for f in $(LEETCODE_FILES); do \
		echo "  - $$f"; \
	done

# Tidy module dependencies
.PHONY: tidy
tidy:
	$(GO) mod tidy

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  all      - Build all leetcode binaries (default)"
	@echo "  run      - Run a specific problem (usage: make run PROG=leetcode_433)"
	@echo "  leetcode_.*  - Run leetcode_.*"
	@echo "  clean    - Remove built binaries"
	@echo "  list     - List all available problems"
	@echo "  tidy     - Tidy Go module dependencies"
