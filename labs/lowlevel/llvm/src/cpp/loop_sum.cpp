// 第一课：循环求和。-O0 与 -O2 的 IR 差别主要来自 mem2reg 与归纳变量化简。
//
//   make ir           生成 bin/clang/loop_sum-O0.ll、-O2.ll、-O3.ll
//
// 看什么：
//   -O0：acc 与 i 各有一个 alloca，每轮 load / add / store 回内存；
//   -O2：alloca 消失，变成 phi；循环边界比较仍在；
//   -O3：与 -O2 接近，但可能进一步展开或向量化。

int sum_to(int n) {
  int acc = 0;
  for (int i = 0; i < n; ++i) {
    acc += i;
  }
  return acc;
}

int main() {
  return sum_to(10) == 45 ? 0 : 1;
}
