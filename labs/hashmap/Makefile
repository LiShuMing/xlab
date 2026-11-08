.PHONY: all test report quick clean
BUILD ?= .local/build
PERFECT_HASH_ROOT ?=
all:
	cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=Release -DPERFECT_HASH_ROOT="$(PERFECT_HASH_ROOT)"
	cmake --build $(BUILD) --parallel 2
test: all
	ctest --test-dir $(BUILD) --output-on-failure
report:
	python3 tools/run.py --suite standard $(if $(PERFECT_HASH_ROOT),--perfect-hash-root "$(PERFECT_HASH_ROOT)")
quick:
	python3 tools/run.py --suite quick $(if $(PERFECT_HASH_ROOT),--perfect-hash-root "$(PERFECT_HASH_ROOT)")
clean:
	cmake --build $(BUILD) --target clean
