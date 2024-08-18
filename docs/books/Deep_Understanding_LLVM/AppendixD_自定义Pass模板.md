# 附录D 自定义Pass模板

## New Pass Manager模板：Analysis Pass

```c++
// MyAnalysis.h
#include "llvm/IR/PassManager.h"
#include "llvm/IR/Function.h"

struct MyAnalysisResult {
  int InstructionCount;
  int BasicBlockCount;
  // ... 分析结果
};

class MyAnalysis : public llvm::AnalysisInfoMixin<MyAnalysis> {
public:
  using Result = MyAnalysisResult;

  Result run(llvm::Function &F, llvm::AnalysisManager<llvm::Function> &AM) {
    Result R;
    R.InstructionCount = 0;
    R.BasicBlockCount = 0;

    for (auto &BB : F) {
      R.BasicBlockCount++;
      for (auto &I : BB)
        R.InstructionCount++;
    }

    return R;
  }

private:
  friend struct llvm::AnalysisInfoMixin<MyAnalysis>;
  static llvm::AnalysisKey Key;
};

// MyAnalysis.cpp
#include "MyAnalysis.h"
llvm::AnalysisKey MyAnalysis::Key;
```

## New Pass Manager模板：Transform Pass

```c++
// MyTransform.h
#include "llvm/IR/PassManager.h"
#include "llvm/IR/Function.h"

class MyTransformPass : public llvm::PassInfoMixin<MyTransformPass> {
public:
  llvm::PreservedAnalyses run(llvm::Function &F,
                               llvm::AnalysisManager<llvm::Function> &AM) {
    // 获取分析结果
    auto &AnalysisResult = AM.getResult<MyAnalysis>(F);

    // 执行变换
    bool Changed = doTransformation(F, AnalysisResult);

    // 返回保留的分析
    if (Changed)
      return llvm::PreservedAnalyses::none();
    else
      return llvm::PreservedAnalyses::all();
  }

  static bool isRequired() { return true; }  // 必需Pass标记

private:
  bool doTransformation(llvm::Function &F, const MyAnalysisResult &AR) {
    bool Changed = false;
    // ... 变换逻辑
    return Changed;
  }
};
```

## PassBuilder注册方法

```c++
// 在PassBuilder中注册自定义Pass

// 方法1: 注册为Pipeline可解析的Pass
extern "C" LLVM_ATTRIBUTE_WEAK void ::llvm::registerPassBuilderCallbacks(
    llvm::PassBuilder &PB) {

  // 注册到-pipelines=文本语法
  PB.registerPipelineParsingCallback(
      [](StringRef Name, llvm::FunctionPassManager &FPM,
         llvm::ArrayRef<llvm::PassBuilder::PipelineElement>) {
        if (Name == "my-transform") {
          FPM.addPass(MyTransformPass());
          return true;
        }
        return false;
      });

  // 注册到优化流水线的扩展点
  PB.registerOptimizerLastEPCallback(
      [](llvm::FunctionPassManager &FPM, llvm::OptimizationLevel Level) {
        if (Level == llvm::OptimizationLevel::O2)
          FPM.addPass(MyTransformPass());
      });
}

// 使用:
// opt -passes='my-transform' input.ll
// 或在O2流水线末尾自动插入
```

## MLIR Pass模板

```c++
// MyMLIRPass.h
#include "mlir/Pass/Pass.h"

struct MyMLIRPass
    : public mlir::PassWrapper<MyMLIRPass,
                                mlir::OperationPass<mlir::func::FuncOp>> {

  void runOnOperation() override {
    auto Func = getOperation();

    // 遍历所有操作
    Func.walk([](mlir::Operation *Op) {
      // 检查操作类型
      if (auto AddOp = llvm::dyn_cast<mlir::arith::AddFOp>(Op)) {
        // 变换逻辑
        rewriteAddOp(AddOp);
      }
    });
  }

  static void rewriteAddOp(mlir::arith::AddFOp Op) {
    mlir::OpBuilder Builder(Op);
    // ... 重写逻辑
  }

  llvm::StringRef getArgument() const override { return "my-mlir-pass"; }
  llvm::StringRef getDescription() const override { return "My MLIR Pass"; }
};

// 注册Pass
void registerMyPass() {
  mlir::registerPass([]() -> std::unique_ptr<mlir::Pass> {
    return std::make_unique<MyMLIRPass>();
  });
}

// 使用:
// mlir-opt --my-mlir-pass input.mlir -o output.mlir
```

## Module级Pass模板

```c++
class MyModulePass : public llvm::PassInfoMixin<MyModulePass> {
public:
  llvm::PreservedAnalyses run(llvm::Module &M,
                               llvm::AnalysisManager<llvm::Module> &AM) {
    bool Changed = false;

    for (auto &F : M) {
      // 跨函数的分析和变换
      if (shouldTransform(F)) {
        transformFunction(F);
        Changed = true;
      }
    }

    return Changed ? llvm::PreservedAnalyses::none()
                   : llvm::PreservedAnalyses::all();
  }

  static bool isRequired() { return true; }
};
```
