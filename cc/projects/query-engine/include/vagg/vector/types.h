#ifndef VAGG_VECTOR_TYPES_H_
#define VAGG_VECTOR_TYPES_H_

#include <cstdint>
#include <string>
#include <string_view>

namespace vagg {

// Primitive type kinds
enum class TypeKind {
  kInt32,
  kInt64,
  kFloat64,
  kUnknown,
};

// Get type kind from string
TypeKind TypeKindFromString(std::string_view s);

// Get type size in bytes
size_t TypeSize(TypeKind kind);

// Type description
struct Type {
  TypeKind kind;
  bool nullable;

  Type() : kind(TypeKind::kUnknown), nullable(false) {}
  Type(TypeKind k, bool n = false) : kind(k), nullable(n) {}

  static Type Int32() { return Type(TypeKind::kInt32, false); }
  static Type Int64() { return Type(TypeKind::kInt64, false); }
  static Type Float64() { return Type(TypeKind::kFloat64, false); }
  static Type NullableInt32() { return Type(TypeKind::kInt32, true); }
  static Type NullableInt64() { return Type(TypeKind::kInt64, true); }

  std::string ToString() const {
    std::string result = TypeKindToString(kind);
    if (nullable) result += " (nullable)";
    return result;
  }

 private:
  static const char* TypeKindToString(TypeKind kind) {
    switch (kind) {
      case TypeKind::kInt32:
        return "INT32";
      case TypeKind::kInt64:
        return "INT64";
      case TypeKind::kFloat64:
        return "FLOAT64";
      default:
        return "UNKNOWN";
    }
  }
};

// Column schema for table definition
struct ColumnSchema {
  std::string name;
  Type type;

  ColumnSchema() : name(), type() {}
  ColumnSchema(std::string n, Type t) : name(std::move(n)), type(std::move(t)) {}

  std::string ToString() const { return name + ": " + type.ToString(); }
};

// Schema for a table or chunk
class Schema {
 public:
  Schema() : columns_() {}

  static Schema FromTypes(const std::vector<Type>& types) {
    Schema schema;
    for (size_t i = 0; i < types.size(); ++i) {
      schema.columns_.push_back(ColumnSchema("col_" + std::to_string(i), types[i]));
    }
    return schema;
  }

  size_t num_columns() const { return columns_.size(); }
  const ColumnSchema& column(size_t i) const { return columns_[i]; }
  const Type& type(size_t i) const { return columns_[i].type; }
  TypeKind kind(size_t i) const { return columns_[i].type.kind; }

  void AddColumn(ColumnSchema col) { columns_.push_back(std::move(col)); }

 private:
  std::vector<ColumnSchema> columns_;
};

}  // namespace vagg

#endif  // VAGG_VECTOR_TYPES_H_
