#include "vagg/vector/vector.h"
#include "vagg/vector/types.h"

namespace vagg {

TypeKind TypeKindFromString(std::string_view s) {
  if (s == "INT32" || s == "int32" || s == "int") {
    return TypeKind::kInt32;
  } else if (s == "INT64" || s == "int64" || s == "long") {
    return TypeKind::kInt64;
  } else if (s == "FLOAT64" || s == "float64" || s == "double") {
    return TypeKind::kFloat64;
  }
  return TypeKind::kUnknown;
}

size_t TypeSize(TypeKind kind) {
  switch (kind) {
    case TypeKind::kInt32:
      return sizeof(int32_t);
    case TypeKind::kInt64:
      return sizeof(int64_t);
    case TypeKind::kFloat64:
      return sizeof(double);
    default:
      return 0;
  }
}

}  // namespace vagg
