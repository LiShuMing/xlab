# gpu-kernel 主题统一入口，只做调度，不写编译细节。
.PHONY: all roofline kernels cuda-graph report test sanitize clean

PYTHON ?= python3

all: roofline kernels cuda-graph report

roofline:
	$(PYTHON) roofline/bench_roofline.py

kernels:
	$(MAKE) -C fused_ops build
	$(PYTHON) fused_ops/bench_fused_ops.py

cuda-graph:
	$(PYTHON) cuda_graph/bench_cuda_graph.py

report:
	$(PYTHON) tools/build_report.py

test:
	$(MAKE) -C fused_ops test
	$(PYTHON) fused_ops/bench_fused_ops.py --test-only
	$(PYTHON) cuda_graph/bench_cuda_graph.py --test-only

sanitize:
	$(MAKE) -C fused_ops sanitize

clean:
	$(MAKE) -C fused_ops clean
