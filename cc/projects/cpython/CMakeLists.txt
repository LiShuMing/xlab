cmake_minimum_required(VERSION 3.12)

project(EmbedPython)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

add_executable(EmbedPython main.cc)

target_include_directories(EmbedPython PRIVATE ${Python3_INCLUDE_DIRS})
target_link_libraries(EmbedPython PRIVATE ${Python3_LIBRARIES})