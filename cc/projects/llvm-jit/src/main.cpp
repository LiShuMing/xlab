#include <iostream>
#include <memory>
#include <vector>

#include "M0_JITSetup.h"
#include "M1_AST.h"
#include "Utils.h"

using namespace llvm_jit;

void printBanner(const std::string& title) {
    std::cout << "\n========================================\n";
    std::cout << "  " << title << "\n";
    std::cout << "========================================\n";
}

void demoM0_JITSetup() {
    printBanner("M0: LLVM JIT Environment Setup");

    JITEnvironment env;
    if (!env.init()) {
        std::cerr << "Failed to initialize JIT environment\n";
        return;
    }

    std::cout << "Target triple: " << env.getTargetTriple() << "\n";
    std::cout << "Data layout: " << env.getDataLayout().getStringRepresentation() << "\n";

    env.shutdown();
    std::cout << "M0 demo completed successfully\n";
}

void demoM1_AST() {
    printBanner("M1: Expression AST");

    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(2.0)),
            ExpressionBuilder::var(1));

    std::cout << "Expression: " << expr->toString() << "\n";

    std::vector<double> input = {3.0, 5.0};
    auto result = expr->eval(input);
    std::cout << "Eval([3.0, 5.0]): " << result.double_val << "\n";

    auto expr2 = ExpressionBuilder::div(ExpressionBuilder::cst(10.0), ExpressionBuilder::cst(2.0));
    std::cout << "Expression: " << expr2->toString() << "\n";
    auto result2 = expr2->eval({});
    std::cout << "Eval([]): " << result2.double_val << "\n";

    std::cout << "M1 demo completed successfully\n";
}

int main() {
    std::cout << "LLVM JIT Expression Fusion - Learning Project\n";
    std::cout << "Platform: macOS ARM64\n";
    std::cout << "=============================================\n";

    demoM0_JITSetup();
    demoM1_AST();

    std::cout << "\n========================================\n";
    std::cout << "All demos completed!\n";
    std::cout << "========================================\n";

    return 0;
}
