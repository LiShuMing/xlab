.PHONY: deps deps-kqueue build test bench
BACKENDS ?= epoll uring
deps:
	bash scripts/bootstrap-liburing.sh
deps-kqueue:
	bash scripts/bootstrap-libkqueue.sh
build:
	bash scripts/build.sh
test:
	ctest --test-dir build/uring --output-on-failure
	ctest --test-dir build/server --output-on-failure
	python3 scripts/integration_test.py --build build/server --backends $(BACKENDS)
bench:
	python3 scripts/benchmark.py --build build --out results/latest --backends $(BACKENDS)
