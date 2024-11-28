message(STATUS "link_libs=${link_libs}")

add_subdirectory(common)
# add_subdirectory(utils)
# add_subdirectory(experiment)

# set(SRC
#    common/consistent_hash.cpp
#    main.cpp
# )
# foreach(src ${SRC})
#    get_filename_component(exe ${src} NAME_WE)
#    add_executable(${exe} ${src})
#    target_link_libraries(${exe} ${link_libs} pthread)
#    list(APPEND main_deps ${exe})
# endforeach()
# add_custom_target(main DEPENDS ${main_deps})

# Create the executable
add_executable(${PROJECT_NAME} main.cc)

