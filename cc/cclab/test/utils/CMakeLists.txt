message(STATUS "link_libs=${link_libs}")
set(TESTS
    os_exec_op_test.cc
    defer_test.cc
    env_var_test.cc
    task_thread_test.cc
)

foreach (src ${TESTS})
    get_filename_component(exe ${src} NAME_WE)

    add_executable(${exe} ${src} )
    target_include_directories(${exe} PRIVATE "../../thirdparty")
    target_link_libraries(${exe} ${link_libs} cc_common pthread gtest absl::node_hash_map Threads::Threads)

    list(APPEND unittest_deps ${exe})
endforeach ()

add_custom_target(utils_unittest DEPENDS ${unittest_deps})
