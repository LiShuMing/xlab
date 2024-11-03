message(STATUS "link_libs=${link_libs}")
set(TESTS
        abseil_test.cpp
        foo_test.cpp
        basic_test.cpp
        lock_problem.cpp
        lock_problem_dining.cpp
        thread_test.cpp
        mpmc_queue_test.cpp
        consistent_hash_test.cpp
        robin_hood_map_test.cpp
        shared_ptr_test.cpp
        skiplist_test.cpp
        skiplist_v2_test.cpp
        )

foreach (src ${TESTS})
    get_filename_component(exe ${src} NAME_WE)

    add_executable(${exe} ${src} )
    target_include_directories(${exe} PRIVATE "../../thirdparty")
    target_link_libraries(${exe} ${link_libs} cc_common pthread gtest absl::node_hash_map Threads::Threads)

    list(APPEND unittest_deps ${exe})
endforeach ()

add_custom_target(unittest DEPENDS ${unittest_deps})
