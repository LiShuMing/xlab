add_executable(${PROJECT_NAME}_benchmark
    benchmark_main.cpp
)

target_link_libraries(${PROJECT_NAME}_benchmark PRIVATE
    ${PROJECT_NAME}_core
    benchmark::benchmark
)

target_include_directories(${PROJECT_NAME}_benchmark PRIVATE
    ${CMAKE_SOURCE_DIR}/include
)

add_test(NAME ${PROJECT_NAME}_benchmark COMMAND ${PROJECT_NAME}_benchmark)
