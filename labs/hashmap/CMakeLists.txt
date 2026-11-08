cmake_minimum_required(VERSION 3.20)
project(hashmap_lab LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
set(PERFECT_HASH_ROOT "" CACHE PATH "Optional local perfect_hash checkout; never downloaded")
option(HASHMAP_SANITIZE "Enable address and undefined behavior sanitizers" OFF)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/generated")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_cases.py"
    --output "${CMAKE_CURRENT_BINARY_DIR}/generated"
    RESULT_VARIABLE generate_status)
if(NOT generate_status EQUAL 0)
    message(FATAL_ERROR "Could not generate deterministic cases")
endif()
add_library(lab_options INTERFACE)
target_include_directories(lab_options INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_BINARY_DIR}/generated")
target_compile_options(lab_options INTERFACE -Wall -Wextra -Wpedantic)
if(HASHMAP_SANITIZE)
    target_compile_options(lab_options INTERFACE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(lab_options INTERFACE -fsanitize=address,undefined)
endif()
add_executable(hashmap_bench bench/main.cc)
target_link_libraries(hashmap_bench PRIVATE lab_options)
if(PERFECT_HASH_ROOT)
    set(ph_header "${PERFECT_HASH_ROOT}/singleheader/perfect_hash.h")
    if(NOT EXISTS "${ph_header}")
        message(FATAL_ERROR "PERFECT_HASH_ROOT must contain singleheader/perfect_hash.h")
    endif()
    target_include_directories(hashmap_bench SYSTEM PRIVATE "${PERFECT_HASH_ROOT}/singleheader")
    target_compile_definitions(hashmap_bench PRIVATE HASHMAP_HAS_PERFECT=1)
    target_sources(hashmap_bench PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated/perfect_cases.cc")
    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        target_compile_options(hashmap_bench PRIVATE -fconstexpr-steps=100000000)
    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        target_compile_options(hashmap_bench PRIVATE -fconstexpr-ops-limit=100000000)
    endif()
endif()
add_executable(hashmap_tests tests/maps_test.cc)
target_link_libraries(hashmap_tests PRIVATE lab_options)
enable_testing()
add_test(NAME map_correctness COMMAND hashmap_tests)
add_test(NAME tooling_correctness COMMAND "${Python3_EXECUTABLE}" -m unittest discover
    -s "${CMAKE_CURRENT_SOURCE_DIR}/tests" -p "test_*.py" -v)
add_test(NAME lookup_contract COMMAND hashmap_bench --method linear --case short64
    --repeat 1 --batch-ms 1 --hit 50)
if(PERFECT_HASH_ROOT)
    foreach(case_name short8 short64 short255 short256 short1024 prefix64)
        add_test(NAME perfect_${case_name} COMMAND hashmap_bench --method perfect --case ${case_name}
            --repeat 1 --batch-ms 1 --hit 50)
    endforeach()
    add_test(NAME wide_contract COMMAND hashmap_bench --method wide --case short64
        --repeat 1 --batch-ms 1 --hit 0)
endif()

# Standalone mechanisms inspired by analytical operators; no StarRocks dependency.
add_executable(hashmap_operators bench/operators.cc)
target_link_libraries(hashmap_operators PRIVATE lab_options)
add_executable(hashmap_operator_tests tests/operator_maps_test.cc)
target_link_libraries(hashmap_operator_tests PRIVATE lab_options)
add_test(NAME operator_correctness COMMAND hashmap_operator_tests)
foreach(method std flat-u64 flat-fp direct)
    add_test(NAME aggregate_${method} COMMAND hashmap_operators --method ${method}
        --case agg-dense8 --mode aggregate --distribution phases --null-percent 10
        --n 4096 --ndv 64 --domain 256 --repeat 1 --batch-ms 1)
endforeach()
foreach(method bucket chain chain-fp direct)
    add_test(NAME join_${method} COMMAND hashmap_operators --method ${method}
        --case join-dense --mode join-probe --n 4096 --ndv 64 --domain 256
        --hit 50 --null-percent 10 --repeat 1 --batch-ms 1)
endforeach()
add_test(NAME bitmap_semijoin COMMAND hashmap_operators --method bitmap --case semi-dense
    --mode semi-probe --n 4096 --ndv 64 --domain 256 --null-percent 10
    --repeat 1 --batch-ms 1)
add_test(NAME composite_serialized COMMAND hashmap_operators --method flat-bytes
    --case agg-composite32x2 --mode aggregate --domain 0 --n 4096 --ndv 512
    --repeat 1 --batch-ms 1)
add_test(NAME operator_csv_contract COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/operator_contract_test.py" "$<TARGET_FILE:hashmap_operators>")

add_executable(hashmap_states bench/states.cc)
target_link_libraries(hashmap_states PRIVATE lab_options)
add_executable(hashmap_state_tests tests/state_maps_test.cc)
target_link_libraries(hashmap_state_tests PRIVATE lab_options)
add_test(NAME state_correctness COMMAND hashmap_state_tests)
add_test(NAME state_csv_contract COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/state_contract_test.py" "$<TARGET_FILE:hashmap_states>")
