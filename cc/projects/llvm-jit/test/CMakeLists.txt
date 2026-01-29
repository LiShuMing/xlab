add_executable(${PROJECT_NAME}_test
    test_main.cpp
    ASTTest.cpp
)

target_link_libraries(${PROJECT_NAME}_test PRIVATE
    ${PROJECT_NAME}_core
    GTest::gtest_main
    GTest::gmock
)

target_include_directories(${PROJECT_NAME}_test PRIVATE
    ${CMAKE_SOURCE_DIR}/include
)

add_test(NAME ${PROJECT_NAME}_test COMMAND ${PROJECT_NAME}_test)
