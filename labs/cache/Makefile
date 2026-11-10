.PHONY: all test quick report
BUILD ?= .local/build
all:
	cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD) --parallel 2
test: all
	ctest --test-dir $(BUILD) --output-on-failure
quick:
	python3 tools/run.py --suite quick
report:
	python3 tools/run.py --suite standard
