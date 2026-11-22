NVCC ?= nvcc
ARCH ?= native
CUDA_FLAGS := -O3 -std=c++17 -arch=$(ARCH) -lineinfo
BIN := bin/cuda_fused_ops

.PHONY: build test sanitize clean

build: $(BIN)

$(BIN): kernels.cu
	@mkdir -p bin
	$(NVCC) $(CUDA_FLAGS) -o $@ $<

test: $(BIN)
	./$(BIN) --test

sanitize: $(BIN)
	compute-sanitizer --tool memcheck ./$(BIN) --test --small
	compute-sanitizer --tool racecheck ./$(BIN) --test --small

clean:
	rm -rf bin
