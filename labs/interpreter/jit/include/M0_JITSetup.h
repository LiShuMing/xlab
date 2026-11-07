#ifndef M0_JIT_SETUP_H
#define M0_JIT_SETUP_H

#include <llvm/ExecutionEngine/Orc/LLJIT.h>
#include <llvm/ExecutionEngine/Orc/ThreadSafeModule.h>
#include <llvm/IR/DataLayout.h>
#include <llvm/Target/TargetMachine.h>

#include <memory>
#include <string>

namespace llvm_jit {

class JITEnvironment {
public:
    JITEnvironment();
    ~JITEnvironment();
    bool init();
    void shutdown();

    llvm::orc::LLJIT& getJIT() { return *jit_; }
    const llvm::DataLayout& getDataLayout() const { return jit_->getDataLayout(); }
    std::string getTargetTriple() const { return jit_->getTargetTriple().getTriple(); }

    template <typename FuncPtr>
    FuncPtr getFunction(const std::string& name) {
        auto symbol = jit_->lookup(name);
        if (!symbol) {
            throw std::runtime_error("Symbol not found: " + name);
        }
        uint64_t addr = static_cast<uint64_t>(symbol->getValue());
        return reinterpret_cast<FuncPtr>(addr);
    }

private:
    std::unique_ptr<llvm::orc::LLJIT> jit_;
    bool initialized_ = false;
};

} // namespace llvm_jit

#endif // M0_JIT_SETUP_H
