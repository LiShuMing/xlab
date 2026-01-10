# Auto-detect benchmark files from bench/ directory
BENCHMARK_SOURCES := $(wildcard bench/bench_*.cpp)
BENCHMARK_NAMES := $(notdir $(BENCHMARK_SOURCES:.cpp=))

.PHONY: all list clean help $(BENCHMARK_NAMES)

# Default target - build and run all benchmarks
all: $(BENCHMARK_NAMES)

# List available benchmarks
list:
	@echo "Available benchmarks:"
	@for name in $(BENCHMARK_NAMES); do echo "  - $$name"; done

# Pattern rule for all detected benchmarks
# Preserves the full name (e.g., bench_memory_cache1) for CMake targets
%:
	@echo "Running benchmark: $@"
	@if [ ! -d "build_RELEASE" ]; then \
		echo "Error: build_RELEASE directory not found. Run 'cmake -B build_RELEASE -DCMAKE_BUILD_TYPE=RELEASE ..' first."; \
		exit 1; \
	fi
	cd build_RELEASE && make bench_$(@F) && ./bench/bench_$(@F)

clean:
	cd build_RELEASE && make clean
	rm -rf build_RELEASE

# Help target
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  all        - Build and run all benchmarks"
	@echo "  list       - List available benchmarks"
	@echo "  <name>     - Build and run specific benchmark"
	@echo "  clean      - Clean build directory"
	@echo "  help       - Show this help message"
	@echo ""
	@echo "Available benchmarks:"
	@for name in $(BENCHMARK_NAMES); do echo "  - $$name"; done