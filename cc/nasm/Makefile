# Auto-detect and build NASM tutorial files
# Supports: Linux (nasm), macOS (clang ARM64), and Windows (nasm)
# Usage: make [target] | make all | make clean

UNAME := $(shell uname)
TUTORIAL_DIR := src/tutorial
BUILD_DIR := $(TUTORIAL_DIR)

# Auto-detect tutorial targets
TUTORIAL_ASM := $(wildcard $(TUTORIAL_DIR)/*.asm)
TUTORIAL_C := $(wildcard $(TUTORIAL_DIR)/*.c)

# Extract base names and get unique targets
TUTORIAL_BASES := $(sort $(foreach f,$(TUTORIAL_ASM),\
    $(basename $(notdir $(f)))))

UNIQUE_TARGETS := $(sort $(foreach t,$(TUTORIAL_BASES),\
    $(patsubst %_linux,%,$(patsubst %_macos,%,$(patsubst %_mac,%,$(t))))))

# Tutorials that only work on Linux (x86_64 syscalls)
LINUX_ONLY := t2 t3 t5 t6 average fib mywrite power square

# Available on macOS (with ARM64 port)
MACOS_AVAILABLE := t1

# Filter out Linux-only tutorials on macOS
ifeq ($(UNAME),Darwin)
    FILTERED_TARGETS := $(filter-out $(LINUX_ONLY),$(UNIQUE_TARGETS))
else
    FILTERED_TARGETS := $(filter-out t5 t6,$(UNIQUE_TARGETS))
endif

TARGETS_BIN := $(FILTERED_TARGETS)

.PHONY: all list help clean $(TARGETS_BIN)

# Default target: build all
all: $(TARGETS_BIN)

# List available tutorials
list:
	@echo "Available tutorials:"
	@for t in $(FILTERED_TARGETS); do \
		echo "  - $$t"; \
	done
	@if [ "$(UNAME)" = "Darwin" ]; then \
		echo ""; \
		echo "Linux-only tutorials (not available on macOS):"; \
		for t in $(LINUX_ONLY); do \
			echo "  - $$t (requires Linux)"; \
		done; \
	fi

# Help target
help:
	@echo "NASM Tutorial Build System"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  all     - Build all tutorials"
	@echo "  list    - List available tutorials"
	@echo "  help    - Show this help"
	@echo "  clean   - Remove build artifacts"
	@echo "  <name>  - Build specific tutorial"
	@echo ""
	@echo "Available tutorials:"
	@for t in $(FILTERED_TARGETS); do \
		echo "  - $$t"; \
	done
	@if [ "$(UNAME)" = "Darwin" ]; then \
		echo ""; \
		echo "Linux-only tutorials (not available on macOS):"; \
		for t in $(LINUX_ONLY); do \
			echo "  - $$t"; \
		done; \
	fi

# Build rules for each target
define BUILD_template
$(1):
	@echo "Building target: $(1) for $(UNAME)"
	@if [ "$(UNAME)" = "Darwin" ]; then \
		echo "  Compiling for macOS (ARM64)..."; \
		if [ -f "$(TUTORIAL_DIR)/$(1)_macos.asm" ]; then \
			echo "  Using: $(TUTORIAL_DIR)/$(1)_macos.asm"; \
			if [ -f "$(TUTORIAL_DIR)/$(1)_main.c" ]; then \
				echo "  With C wrapper: $(TUTORIAL_DIR)/$(1)_main.c"; \
				clang -o $(1) $(TUTORIAL_DIR)/$(1)_macos.asm $(TUTORIAL_DIR)/$(1)_main.c; \
			else \
				clang -o $(1) $(TUTORIAL_DIR)/$(1)_macos.asm; \
			fi; \
		elif [ -f "$(TUTORIAL_DIR)/$(1).asm" ]; then \
			echo "  Using: $(TUTORIAL_DIR)/$(1).asm"; \
			clang -o $(1) $(TUTORIAL_DIR)/$(1).asm; \
		else \
			echo "  ERROR: No source file found for '$(1)'"; \
			exit 1; \
		fi; \
	else \
		echo "  Compiling for Linux (x86_64)..."; \
		if [ -f "$(TUTORIAL_DIR)/$(1)_linux.asm" ]; then \
			echo "  Using: $(TUTORIAL_DIR)/$(1)_linux.asm"; \
			nasm -f elf64 -o $(BUILD_DIR)/$(1).o $(TUTORIAL_DIR)/$(1)_linux.asm && \
			ld -o $(1) $(BUILD_DIR)/$(1).o; \
		elif [ -f "$(TUTORIAL_DIR)/$(1).asm" ]; then \
			echo "  Using: $(TUTORIAL_DIR)/$(1).asm"; \
			nasm -f elf64 -o $(BUILD_DIR)/$(1).o $(TUTORIAL_DIR)/$(1).asm && \
			ld -o $(1) $(BUILD_DIR)/$(1).o; \
		else \
			echo "  ERROR: No source file found for '$(1)'"; \
			exit 1; \
		fi; \
	fi
	@./$(1) || true
endef

$(foreach t,$(FILTERED_TARGETS),$(eval $(call BUILD_template,$(t))))

# Clean target
clean:
	rm -f $(patsubst %,$(BUILD_DIR)/%.o,$(FILTERED_TARGETS)) $(FILTERED_TARGETS)
	@echo "Cleaned build artifacts"
