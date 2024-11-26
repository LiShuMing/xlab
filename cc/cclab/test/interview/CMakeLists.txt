message(STATUS "link_libs=${link_libs}")
set(interview
    interview_test.cc
)

foreach (src ${interview})
    get_filename_component(exe ${src} NAME_WE)

    add_executable(${exe} ${src} )
    target_include_directories(${exe} PRIVATE "../../thirdparty")
    target_link_libraries(${exe} ${link_libs} cc_common pthread gtest absl::node_hash_map Threads::Threads)

    list(APPEND interview_deps ${exe})
endforeach ()

add_custom_target(interview_unittest DEPENDS ${interview_deps})
