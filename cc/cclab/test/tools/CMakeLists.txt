# message(STATUS "link_libs=${link_libs}")

# set(COMMON_TESTS
#     abseil_test.cc
#     foo_test.cc
#     basic_test.cc
#     lock_problem.cc
#     lock_problem_dining.cc
#     thread_test.cc
#     mpmc_queue_test.cc
#     consistent_hash_test.cc
#     robin_hood_map_test.cc
#     shared_ptr_test.cc
#     skiplist_test.cc
#     skiplist_v2_test.cc
#     bplusplustree_test.cc
#     btree_test.cc
#     string_test.cc
#     bthread_test.cc
#     coroutine_test.cc
#     math_test.cc
# )

# foreach (src ${COMMON_TESTS})
#     get_filename_component(exe common_${src} NAME_WE)
#     add_executable(${exe} ${src} )
#     target_include_directories(${exe} PRIVATE "../../thirdparty")
#     target_link_libraries(${exe} ${link_libs} PRIVATE common pthread gtest absl::node_hash_map Threads::Threads)
#     list(APPEND unittest_deps ${exe})
# endforeach ()

# add_custom_target(common_unittest DEPENDS ${unittest_deps})

add_directory_for_each_test("${CMAKE_SOURCE_DIR}/test/tools")