cmake_minimum_required(VERSION 3.16)

set(GTest_DIR "${THIRDPARTY_ROOT}/installed/lib/cmake/GTest")
find_package(GTest CONFIG QUIET)

set(Boost_USE_STATIC_LIBS ON)
set(Boost_USE_STATIC_RUNTIME ON)
set(Boost_NO_WARN_NEW_VERSIONS ON)
set(Boost_DIR "${THIRDPARTY_ROOT}/installed/lib/cmake/Boost-1.80.0")
find_package(Boost 1.80 QUIET COMPONENTS system filesystem)

message(STATUS "GTest_FOUND: ${GTest_FOUND}")
message(STATUS "Boost_FOUND: ${Boost_FOUND}")

if(GTest_FOUND)
    set(_srlab_gtest_target "")
    set(_srlab_require_custom_main OFF)
    if(TARGET GTest::gtest_main)
        set(_srlab_gtest_target GTest::gtest_main)
        message(STATUS "Using GTest::gtest_main")
    elseif(TARGET GTest::gtest)
        set(_srlab_gtest_target GTest::gtest)
        set(_srlab_require_custom_main ON)
        message(STATUS "Using GTest::gtest (custom main required)")
    endif()

    if(_srlab_gtest_target)
        add_executable(use_arrow_tests test_arrow.cpp)
        set_target_properties(use_arrow_tests PROPERTIES
            CXX_STANDARD 17
            CXX_STANDARD_REQUIRED ON
            CXX_EXTENSIONS OFF)
        
        target_include_directories(use_arrow_tests PRIVATE
            "${THIRDPARTY_ROOT}/installed/include")
        
        target_link_libraries(use_arrow_tests PRIVATE
            ${_srlab_gtest_target}
            "${THIRDPARTY_ROOT}/installed/lib64/libarrow.a"
            "${THIRDPARTY_ROOT}/installed/lib64/libarrow_bundled_dependencies.a"
            "${THIRDPARTY_ROOT}/installed/lib/libz.a"
            "${THIRDPARTY_ROOT}/installed/lib/liblz4.a"
            "${THIRDPARTY_ROOT}/installed/lib64/libsnappy.a"
            "${THIRDPARTY_ROOT}/installed/lib64/libbrotlienc.a"
            "${THIRDPARTY_ROOT}/installed/lib64/libbrotlidec.a"
            "${THIRDPARTY_ROOT}/installed/lib64/libbrotlicommon.a"
            pthread
            dl)
        
        if(_srlab_require_custom_main)
            target_compile_definitions(use_arrow_tests PRIVATE SRLAB_NEEDS_GTEST_MAIN=1)
        endif()
        
        add_test(NAME use_arrow COMMAND use_arrow_tests)
        message(STATUS "Added test: use_arrow")
        
        if(Boost_FOUND)
            add_executable(use_boost_tests test_boost.cpp)
            set_target_properties(use_boost_tests PROPERTIES
                CXX_STANDARD 17
                CXX_STANDARD_REQUIRED ON
                CXX_EXTENSIONS OFF)
            
            target_link_libraries(use_boost_tests PRIVATE
                ${_srlab_gtest_target}
                Boost::system
                Boost::filesystem)
            
            if(_srlab_require_custom_main)
                target_compile_definitions(use_boost_tests PRIVATE SRLAB_NEEDS_GTEST_MAIN=1)
            endif()
            
            add_test(NAME use_boost COMMAND use_boost_tests)
            message(STATUS "Added test: use_boost")
        else()
            message(STATUS "Boost not found; skipping Boost tests.")
        endif()
    else()
        message(WARNING "GTest package found but exposes no gtest/gmock target; skipping tests.")
    endif()
else()
    message(STATUS "GTest package not found at ${GTest_DIR}")
endif()

unset(_srlab_gtest_target)
unset(_srlab_require_custom_main)

