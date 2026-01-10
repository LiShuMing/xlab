BENCHMARKS := bench_basic bench_cpu_performance bench_memory_cache bench_allocator

$(BENCHMARKS):
	cd build_RELEASE && make $(@)
	./build_RELEASE/bench/$(@)

clean:
	cd build_RELEASE && make clean
	rm -rf build_RELEASE