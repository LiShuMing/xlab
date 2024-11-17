message(STATUS "link_libs=${link_libs}")

add_subdirectory(tools)

set(SRC
   tools/select_server.cpp
   tools/epoll_server.cpp
)
foreach(src ${SRC})
   get_filename_component(exe ${src} NAME_WE)
   add_executable(${exe} ${src})
   target_link_libraries(${exe} ${link_libs} pthread)
   list(APPEND main_deps ${exe})
endforeach()
add_custom_target(main DEPENDS ${main_deps})