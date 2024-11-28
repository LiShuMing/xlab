message(STATUS "link_libs=${link_libs}")

# set(interview
#     interview1_test.cc
# )

# foreach (src ${interview})
#     get_filename_component(exe interview_${src} NAME_WE)

#     add_executable(${exe} ${src} )
#     target_include_directories(${exe} PRIVATE "../../thirdparty")
#     target_link_libraries(${exe} ${link_libs} PRIVATE common pthread gtest absl::node_hash_map Threads::Threads)

#     list(APPEND interview_deps ${exe})
# endforeach ()

# add_custom_target(interview_unittest DEPENDS ${interview_deps})

message(STATUS "CMAKE_SOURCE_DIR=${CMAKE_SOURCE_DIR}")
add_directory_tests("${CMAKE_SOURCE_DIR}/test/interview")
