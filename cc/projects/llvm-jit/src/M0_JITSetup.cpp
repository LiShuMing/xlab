#include "M0_JITSetup.h"

#include <llvm/Support/Error.h>
#include <llvm/Support/TargetSelect.h>

#include <iostream>

namespace llvm_jit {

JITEnvironment::JITEnvironment() = default;

JITEnvironment::~JITEnvironment() {
    shutdown();
}

bool JITEnvironment::init() {
    if (initialized_) {
        std::cerr << "JITEnvironment already initialized\n";
        return false;
    }

    llvm::InitializeNativeTarget();
    llvm::InitializeNativeTargetAsmPrinter();
    llvm::InitializeNativeTargetAsmParser();

    auto JITBuilder = llvm::orc::LLJITBuilder();
    auto JITOrcErr = JITBuilder.create();
    if (auto Err = JITOrcErr.takeError()) {
        std::cerr << "Failed to create LLJIT: " << llvm::toString(std::move(Err)) << "\n";
        return false;
    }
    jit_ = std::move(JITOrcErr.get());

    std::cout << "Target triple: " << getTargetTriple() << "\n";
    std::cout << "Data layout: " << getDataLayout().getStringRepresentation() << "\n";

    initialized_ = true;
    std::cout << "JITEnvironment initialized successfully\n";
    return true;
}

void JITEnvironment::shutdown() {
    if (initialized_) {
        jit_.reset();
        initialized_ = false;
    }
}

} // namespace llvm_jit
