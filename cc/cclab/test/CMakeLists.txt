message(STATUS "link_libs=${link_libs}")
set(TESTS
        abseil_test.cc
        foo_test.cc
        basic_test.cc
        lock_problem.cc
        lock_problem_dining.cc
        thread_test.cc
        mpmc_queue_test.cc
        consistent_hash_test.cc
        robin_hood_map_test.cc
        shared_ptr_test.cc
        skiplist_test.cc
        skiplist_v2_test.cc
        )

foreach (src ${TESTS})
    get_filename_component(exe ${src} NAME_WE)

    add_executable(${exe} ${src} )
    target_include_directories(${exe} PRIVATE "../../thirdparty")
    target_link_libraries(${exe} ${link_libs} cc_common pthread gtest absl::node_hash_map Threads::Threads)

    list(APPEND unittest_deps ${exe})
endforeach ()

add_custom_target(unittest DEPENDS ${unittest_deps})
