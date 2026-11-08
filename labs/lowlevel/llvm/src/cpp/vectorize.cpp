// 第四课：向量化。可向量化循环在 -O3 下变成 <4 x i32> 的 SIMD（Single Instruction
// Multiple Data，单指令多数据）指令，与 labs/lowlevel/simd 里的手写内建函数形成对照。
//
// 看什么：
//   -O0：逐元素的 load / mul / add / store；
//   -O3：出现 vector.ph / vector.body、宽向量运算与 llvm.vector.reduce，
//        循环步长从 1 变成 4 或 8；
//   想确认"向量化确实发生了"，用：
//        clang -O3 -Rpass=loop-vectorize -S -emit-llvm src/cpp/vectorize.cpp -o -
//
// 同样的语义在 -O2 下可能只剩 SLP（Superword-Level Parallelism）向量化，
// 这就是 -O2 与 -O3 在 IR 层面最直观的差别之一。

void scale_add(const int* a, const int* b, int* out, int n) {
  for (int i = 0; i < n; ++i) {
    out[i] = a[i] * 3 + b[i];
  }
}

int main() {
  int a[8] = {1, 2, 3, 4, 5, 6, 7, 8};
  int b[8] = {1, 1, 1, 1, 1, 1, 1, 1};
  int out[8] = {0};
  scale_add(a, b, out, 8);
  return out[0] == 4 && out[7] == 25 ? 0 : 1;
}
