message(STATUS "link_libs=${link_libs}")

add_library(bench_lib
    common/bench_v2.cpp
)

# Auto-detect all benchmark files from current directory
file(GLOB BENCHMARKS LIST_DIRECTORIES false CONFIGURE_DEPENDS "bench_*.cpp")

message(STATUS "Auto-detected benchmarks: ${BENCHMARKS}")

# for each benchmark generate a target
foreach (src ${BENCHMARKS})
    get_filename_component(exe ${src} NAME_WE)
    add_executable(${exe} ${src})
    target_link_libraries(${exe} PRIVATE ${link_libs} benchmark pthread bench_lib)
    list(APPEND benchmarks_deps ${exe})
endforeach ()

add_custom_target(bench DEPENDS ${benchmarks_deps})


