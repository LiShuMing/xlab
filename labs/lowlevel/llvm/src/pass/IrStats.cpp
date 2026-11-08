// 自写 pass 之一：只读统计。用来学 new PM（New Pass Manager）里怎么遍历 IR。
//
// 构建：make plugin            产物：bin/passes/IrStats.so
// 运行：opt -load-pass-plugin=bin/passes/IrStats.so -passes=ir-stats
//           -disable-output src/ir/04_loop_invariant.ll
//
// 看三件事：
//   1. 一个 pass 只要满足 PassInfoMixin 就有 run() 与名字，注册后即可被 -passes= 调用；
//   2. 只读 pass 返回 PreservedAnalyses::all()，告诉框架"什么都没变"；
//   3. 统计结果打到 stderr，避免和 stdout 上的 IR 混在一起。

#include "llvm/IR/Function.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/Compiler.h"
#include "llvm/Support/raw_ostream.h"

using llvm::AllocaInst;
using llvm::ArrayRef;
using llvm::BasicBlock;
using llvm::CallBase;
using llvm::errs;
using llvm::Function;
using llvm::FunctionAnalysisManager;
using llvm::FunctionPassManager;
using llvm::Instruction;
using llvm::isa;
using llvm::LoadInst;
using llvm::PassBuilder;
using llvm::PassInfoMixin;
using llvm::PassPluginLibraryInfo;
using llvm::PHINode;
using llvm::PreservedAnalyses;
using llvm::StoreInst;
using llvm::StringRef;

namespace {

struct FunctionStats {
  unsigned blocks = 0;
  unsigned instructions = 0;
  unsigned phis = 0;
  unsigned memory_ops = 0;
  unsigned calls = 0;
};

FunctionStats Count(const Function& function) {
  FunctionStats stats;
  for (const BasicBlock& block : function) {
    ++stats.blocks;
    for (const Instruction& instruction : block) {
      ++stats.instructions;
      if (isa<PHINode>(instruction)) {
        ++stats.phis;
      }
      if (isa<LoadInst>(instruction) || isa<StoreInst>(instruction) ||
          isa<AllocaInst>(instruction)) {
        ++stats.memory_ops;
      }
      if (isa<CallBase>(instruction)) {
        ++stats.calls;
      }
    }
  }
  return stats;
}

struct IrStatsPass : PassInfoMixin<IrStatsPass> {
  PreservedAnalyses run(Function& function, FunctionAnalysisManager&) {
    if (function.isDeclaration()) {
      return PreservedAnalyses::all();
    }
    const FunctionStats stats = Count(function);
    errs() << "[ir-stats] " << function.getName() << ": " << stats.instructions
           << " instructions, " << stats.blocks << " blocks, " << stats.phis << " phi, "
           << stats.memory_ops << " memory ops, " << stats.calls << " calls\n";
    return PreservedAnalyses::all();
  }

  // 返回 true 表示即使函数带 optnone 属性也要运行，方便在 -O0 产物上做统计。
  static bool isRequired() { return true; }
};

}  // namespace

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "ir-stats", LLVM_VERSION_STRING, [](PassBuilder& builder) {
            builder.registerPipelineParsingCallback(
                [](StringRef name, FunctionPassManager& function_pm,
                   ArrayRef<PassBuilder::PipelineElement>) {
                  if (name != "ir-stats") {
                    return false;
                  }
                  function_pm.addPass(IrStatsPass());
                  return true;
                });
          }};
}
