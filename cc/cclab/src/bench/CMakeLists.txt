message(STATUS "link_libs=${link_libs}")

add_library(bench_lib
    common/bench_v2.cpp
)

set(BENCHMARKS
    bench_allocator.cpp
    bench_basic.cpp
    bench_memory_cache.cpp
    bench_cpu_performance.cpp
    queue/bench_queue.cpp
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

file(GLOB SRC_BENCHMARKS "hashmap/benchmarks/*.cpp")
file(GLOB SRC_APP "hashmap/app/*.cpp")
file(GLOB INC_HASHES "hashmap/hashes/*")
file(GLOB INC_MAPS "hashmap/maps/*")

# create targets for all map - hash pairs
foreach(MAP_DIR ${INC_MAPS})
    get_filename_component(MAP_NAME ${MAP_DIR} NAME_WE)
    message (STATUS "map_dir=${MAP_DIR}, map_name=${MAP_NAME}")

    foreach(HASH_DIR ${INC_HASHES})
        message(STATUS "hash_dir=${HASH_DIR}")

        # executable name: mapname_hashname
        get_filename_component(HASH_NAME ${HASH_DIR} NAME_WE)
        set(EXECUTABLE_NAME "bench_${MAP_NAME}__${HASH_NAME}")

        # collect .cpp files in current hash and map directory
        file(GLOB SRC_MAP_DIR "${MAP_DIR}/*.cpp")
        file(GLOB SRC_HASH_DIR "${HASH_DIR}/*.cpp")

        add_executable(${EXECUTABLE_NAME} ${SRC_APP} ${SRC_BENCHMARKS} ${SRC_MAP_DIR} ${SRC_HASH_DIR})
        target_include_directories(${EXECUTABLE_NAME} PRIVATE "hashmap/app" "../../thirdparty" ${MAP_DIR} ${HASH_DIR} ${FOLLY_DIR})

        if (EXISTS "${MAP_DIR}/dependencies.cmake")
            include("${MAP_DIR}/dependencies.cmake")
        endif ()

        if (EXISTS "${HASH_DIR}/dependencies.cmake")
            include("${HASH_DIR}/dependencies.cmake")
        endif ()

    endforeach(HASH_DIR ${INC_HASHES})
endforeach(MAP_DIR ${INC_MAPS})
