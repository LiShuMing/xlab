add_library(${PROJECT_NAME}_core
    STATIC
    M1_AST.cpp
    M0_JITSetup.cpp
)

target_link_libraries(${PROJECT_NAME}_core PUBLIC
    LLVMSupport
    LLVMCore
    LLVMExecutionEngine
    LLVMOrcShared
    LLVMOrcJIT
    LLVMTarget
    LLVMAnalysis
    LLVMAArch64AsmParser
    LLVMAArch64CodeGen
    LLVMAArch64Desc
    LLVMAArch64Info
    LLVMAArch64Utils
    LLVMAArch64Disassembler
)

if(APPLE)
    target_link_libraries(${PROJECT_NAME}_core PUBLIC
        "-Wl,-rpath,/opt/homebrew/Cellar/llvm/21.1.8/lib")
endif()

add_executable(${PROJECT_NAME}
    main.cpp
)

target_link_libraries(${PROJECT_NAME} PRIVATE
    ${PROJECT_NAME}_core
)
