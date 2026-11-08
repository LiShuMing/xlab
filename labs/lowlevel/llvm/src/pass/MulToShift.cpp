// 自写 pass 之二：改写 IR。把"乘以 2 的幂"换成左移，教怎么安全地动 IR。
//
// 构建：make plugin            产物：bin/passes/MulToShift.so
// 运行：opt -load-pass-plugin=bin/passes/MulToShift.so -passes=mul-to-shift
//           -S src/ir/01_basics.ll -o -
//
// 看三件事：
//   1. 改 IR 的四步：造新指令 → replaceAllUsesWith → eraseFromParent → 声明分析失效；
//   2. 边遍历边删除必须用 make_early_inc_range，否则迭代器失效；
//   3. 改完返回 PreservedAnalyses::none()，框架会重算后续分析；返回 all() 会让
//      后面的 pass（例如 gvn）读到过期的支配树或别名信息而算错。

#include "llvm/ADT/APInt.h"
#include "llvm/ADT/STLExtras.h"
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/Compiler.h"
#include "llvm/Support/raw_ostream.h"

using llvm::APInt;
using llvm::ArrayRef;
using llvm::BasicBlock;
using llvm::BinaryOperator;
using llvm::ConstantInt;
using llvm::dyn_cast;
using llvm::errs;
using llvm::Function;
using llvm::FunctionAnalysisManager;
using llvm::FunctionPassManager;
using llvm::Instruction;
using llvm::IRBuilder;
using llvm::make_early_inc_range;
using llvm::PassBuilder;
using llvm::PassInfoMixin;
using llvm::PassPluginLibraryInfo;
using llvm::PreservedAnalyses;
using llvm::StringRef;
using llvm::Twine;
using llvm::Value;

namespace {

bool IsPowerOfTwoShift(const ConstantInt* multiplier, unsigned& shift) {
  if (multiplier == nullptr || !multiplier->getValue().isPowerOf2()) {
    return false;
  }
  shift = multiplier->getValue().logBase2();
  // 乘 1 换成移位没有收益，留给 instcombine。
  return shift != 0;
}

struct MulToShiftPass : PassInfoMixin<MulToShiftPass> {
  PreservedAnalyses run(Function& function, FunctionAnalysisManager&) {
    bool changed = false;
    for (BasicBlock& block : function) {
      for (Instruction& instruction : make_early_inc_range(block)) {
        auto* mul = dyn_cast<BinaryOperator>(&instruction);
        if (mul == nullptr || mul->getOpcode() != Instruction::Mul) {
          continue;
        }
        // 乘法可交换，常量可能在左也可能在右。
        for (unsigned constant_index : {1u, 0u}) {
          auto* multiplier = dyn_cast<ConstantInt>(mul->getOperand(constant_index));
          unsigned shift = 0;
          if (!IsPowerOfTwoShift(multiplier, shift)) {
            continue;
          }
          // 常量在 eraseFromParent 之后仍可用（它是 uniqued 对象），但值先拷出来更省心。
          const APInt factor = multiplier->getValue();
          IRBuilder<> builder(mul);
          Value* shifted = builder.CreateShl(
              mul->getOperand(1 - constant_index), ConstantInt::get(mul->getType(), shift),
              Twine(mul->getName()) + ".shl");
          mul->replaceAllUsesWith(shifted);
          mul->eraseFromParent();
          changed = true;
          errs() << "[mul-to-shift] " << function.getName() << ": mul by " << factor
                 << " -> shl " << shift << "\n";
          break;
        }
      }
    }
    return changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }

  static bool isRequired() { return true; }
};

}  // namespace

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "mul-to-shift", LLVM_VERSION_STRING, [](PassBuilder& builder) {
            builder.registerPipelineParsingCallback(
                [](StringRef name, FunctionPassManager& function_pm,
                   ArrayRef<PassBuilder::PipelineElement>) {
                  if (name != "mul-to-shift") {
                    return false;
                  }
                  function_pm.addPass(MulToShiftPass());
                  return true;
                });
          }};
}
