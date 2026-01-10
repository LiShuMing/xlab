message(STATUS "link_libs=${link_libs}")

add_library(bench_lib
    common/bench_v2.cpp
)

set(BENCHMARKS
    bench_allocator.cpp
    bench_basic.cpp
    bench_memory_cache1.cpp
    bench_memory_cache2.cpp
    bench_cpu_performance.cpp
)

# for each benchmark generate a target link lib
foreach (src ${BENCHMARKS})
    # get_filename_component(exe bench_${src} NAME_WE)
    get_filename_component(exe ${src} NAME_WE)
    add_executable(${exe} ${src})
    target_link_libraries(${exe} PRIVATE ${link_libs} benchmark pthread bench_lib)
    list(APPEND benchmarks_deps ${exe})
endforeach ()

add_custom_target(bench DEPENDS ${benchmarks_deps})


