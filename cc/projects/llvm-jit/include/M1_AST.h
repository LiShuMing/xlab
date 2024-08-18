#include <memory>
#include <string>
#include <vector>

namespace llvm_jit {

enum class DataType { Int64, Double, Invalid };

struct Value {
    DataType type;
    double double_val;
    int64_t int64_val;
    bool is_valid;

    static Value from_double(double v) {
        Value r;
        r.type = DataType::Double;
        r.double_val = v;
        r.int64_val = 0;
        r.is_valid = true;
        return r;
    }
    static Value from_int64(int64_t v) {
        Value r;
        r.type = DataType::Int64;
        r.double_val = 0.0;
        r.int64_val = v;
        r.is_valid = true;
        return r;
    }
    static Value null() {
        Value r;
        r.type = DataType::Invalid;
        r.double_val = 0.0;
        r.int64_val = 0;
        r.is_valid = false;
        return r;
    }
};

class Expr {
public:
    virtual ~Expr() = default;
    virtual DataType getType() const = 0;
    virtual Value eval(const std::vector<double>& input) const noexcept = 0;
    virtual std::string toString() const = 0;
    virtual std::unique_ptr<Expr> clone() const = 0;
};

class ConstExpr : public Expr {
public:
    explicit ConstExpr(double v) : val_(v) {}

    DataType getType() const override { return DataType::Double; }
    Value eval(const std::vector<double>&) const noexcept override {
        return Value::from_double(val_);
    }
    std::string toString() const override { return std::to_string(val_); }
    std::unique_ptr<Expr> clone() const override {
        return std::unique_ptr<Expr>(new ConstExpr(val_));
    }

private:
    double val_;
};

class VarExpr : public Expr {
public:
    explicit VarExpr(size_t i) : idx_(i) {}

    DataType getType() const override { return DataType::Double; }
    Value eval(const std::vector<double>& input) const noexcept override {
        if (idx_ < input.size()) return Value::from_double(input[idx_]);
        return Value::null();
    }
    std::string toString() const override { return "v" + std::to_string(idx_); }
    std::unique_ptr<Expr> clone() const override {
        return std::unique_ptr<Expr>(new VarExpr(idx_));
    }
    size_t getIndex() const { return idx_; }

private:
    size_t idx_;
};

enum Op { Add, Sub, Mul, Div };

class BinaryExpr : public Expr {
public:
    BinaryExpr(std::unique_ptr<Expr> l, std::unique_ptr<Expr> r, Op o)
            : left_(std::move(l)), right_(std::move(r)), op_(o) {}

    DataType getType() const override { return DataType::Double; }
    Value eval(const std::vector<double>& input) const noexcept override {
        auto l = left_->eval(input);
        auto r = right_->eval(input);
        if (!l.is_valid || !r.is_valid) return Value::null();

        double res = 0.0;
        switch (op_) {
        case Add:
            res = l.double_val + r.double_val;
            break;
        case Sub:
            res = l.double_val - r.double_val;
            break;
        case Mul:
            res = l.double_val * r.double_val;
            break;
        case Div:
            res = r.double_val != 0.0 ? l.double_val / r.double_val : 0.0;
            break;
        }
        return Value::from_double(res);
    }
    std::string toString() const override {
        const char* s[] = {"+", "-", "*", "/"};
        return "(" + left_->toString() + s[op_] + right_->toString() + ")";
    }
    std::unique_ptr<Expr> clone() const override {
        return std::unique_ptr<Expr>(new BinaryExpr(left_->clone(), right_->clone(), op_));
    }
    Expr* getLeft() const { return left_.get(); }
    Expr* getRight() const { return right_.get(); }
    Op getOp() const { return op_; }

private:
    std::unique_ptr<Expr> left_;
    std::unique_ptr<Expr> right_;
    Op op_;
};

class ExpressionBuilder {
public:
    static std::unique_ptr<Expr> var(size_t i) { return std::unique_ptr<Expr>(new VarExpr(i)); }
    static std::unique_ptr<Expr> cst(double v) { return std::unique_ptr<Expr>(new ConstExpr(v)); }
    static std::unique_ptr<Expr> add(std::unique_ptr<Expr> l, std::unique_ptr<Expr> r) {
        return std::unique_ptr<Expr>(new BinaryExpr(std::move(l), std::move(r), Add));
    }
    static std::unique_ptr<Expr> sub(std::unique_ptr<Expr> l, std::unique_ptr<Expr> r) {
        return std::unique_ptr<Expr>(new BinaryExpr(std::move(l), std::move(r), Sub));
    }
    static std::unique_ptr<Expr> mul(std::unique_ptr<Expr> l, std::unique_ptr<Expr> r) {
        return std::unique_ptr<Expr>(new BinaryExpr(std::move(l), std::move(r), Mul));
    }
    static std::unique_ptr<Expr> div(std::unique_ptr<Expr> l, std::unique_ptr<Expr> r) {
        return std::unique_ptr<Expr>(new BinaryExpr(std::move(l), std::move(r), Div));
    }
};

} // namespace llvm_jit
