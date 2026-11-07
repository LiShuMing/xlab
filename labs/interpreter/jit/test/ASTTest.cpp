#include <gtest/gtest.h>

#include <memory>
#include <vector>

#include "M1_AST.h"

using namespace llvm_jit;

TEST(ASTTest, ConstExpression) {
    auto cst = ExpressionBuilder::cst(42.0);
    EXPECT_EQ(cst->getType(), DataType::Double);
    auto result = cst->eval({});
    EXPECT_DOUBLE_EQ(result.double_val, 42.0);
}

TEST(ASTTest, VariableExpression) {
    auto var = ExpressionBuilder::var(0);
    EXPECT_EQ(var->getType(), DataType::Double);
    auto result = var->eval({3.0});
    EXPECT_DOUBLE_EQ(result.double_val, 3.0);
}

TEST(ASTTest, VariableOutOfBounds) {
    auto var = ExpressionBuilder::var(5);
    auto result = var->eval({1.0, 2.0});
    EXPECT_FALSE(result.is_valid);
}

TEST(ASTTest, AddExpression) {
    auto expr = ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::cst(5.0));
    auto result = expr->eval({2.0});
    EXPECT_DOUBLE_EQ(result.double_val, 7.0);
}

TEST(ASTTest, SubtractExpression) {
    auto expr = ExpressionBuilder::sub(ExpressionBuilder::var(0), ExpressionBuilder::cst(3.0));
    auto result = expr->eval({10.0});
    EXPECT_DOUBLE_EQ(result.double_val, 7.0);
}

TEST(ASTTest, MultiplyExpression) {
    auto expr = ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(4.0));
    auto result = expr->eval({3.0});
    EXPECT_DOUBLE_EQ(result.double_val, 12.0);
}

TEST(ASTTest, DivideExpression) {
    auto expr = ExpressionBuilder::div(ExpressionBuilder::cst(20.0), ExpressionBuilder::cst(4.0));
    auto result = expr->eval({});
    EXPECT_DOUBLE_EQ(result.double_val, 5.0);
}

TEST(ASTTest, DivideByZero) {
    auto expr = ExpressionBuilder::div(ExpressionBuilder::cst(10.0), ExpressionBuilder::cst(0.0));
    auto result = expr->eval({});
    EXPECT_DOUBLE_EQ(result.double_val, 0.0);
}

TEST(ASTTest, ComplexExpression) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::mul(ExpressionBuilder::var(0), ExpressionBuilder::cst(2.0)),
            ExpressionBuilder::var(1));
    auto result = expr->eval({3.0, 5.0});
    EXPECT_DOUBLE_EQ(result.double_val, 11.0);
}

TEST(ASTTest, CloneExpression) {
    auto expr = ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::cst(1.0));
    auto cloned = expr->clone();
    auto result1 = expr->eval({5.0});
    auto result2 = cloned->eval({5.0});
    EXPECT_DOUBLE_EQ(result1.double_val, result2.double_val);
}

TEST(ASTTest, ToString) {
    auto expr = ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::cst(1.0));
    EXPECT_EQ(expr->toString(), "(v0+1.000000)");
}

TEST(ASTTest, NestedExpression) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::cst(1.0)),
            ExpressionBuilder::cst(2.0));
    auto result = expr->eval({3.0});
    EXPECT_DOUBLE_EQ(result.double_val, 6.0);
}

TEST(ASTTest, MultipleVariables) {
    auto expr = ExpressionBuilder::add(
            ExpressionBuilder::add(ExpressionBuilder::var(0), ExpressionBuilder::var(1)),
            ExpressionBuilder::var(2));
    auto result = expr->eval({1.0, 2.0, 3.0});
    EXPECT_DOUBLE_EQ(result.double_val, 6.0);
}

TEST(ValueTest, FromDouble) {
    auto v = Value::from_double(3.14);
    EXPECT_EQ(v.type, DataType::Double);
    EXPECT_DOUBLE_EQ(v.double_val, 3.14);
    EXPECT_TRUE(v.is_valid);
}

TEST(ValueTest, FromInt64) {
    auto v = Value::from_int64(42);
    EXPECT_EQ(v.type, DataType::Int64);
    EXPECT_EQ(v.int64_val, 42);
    EXPECT_TRUE(v.is_valid);
}

TEST(ValueTest, Null) {
    auto v = Value::null();
    EXPECT_EQ(v.type, DataType::Invalid);
    EXPECT_FALSE(v.is_valid);
}
