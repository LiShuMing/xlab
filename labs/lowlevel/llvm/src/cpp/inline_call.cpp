// 第三课：内联（inline）与函数边界。
//
// 看什么：
//   -O0：sum_squares 里每轮都是 call @square；
//   -O2：square 被内联，call 消失，循环体只剩 mul/add/br；
//   -O2 的 IR 里再搜 @square，只剩一个无人调用的定义（或已被删除）。
//
// 这一课对应 pass pipeline 里的 cgscc(inline) 阶段：内联本身不改语义，
// 但它让后面的 instcombine / licm 能在更大的作用域里做优化。

static int square(int x) {
  return x * x;
}

int sum_squares(int n) {
  int acc = 0;
  for (int i = 1; i <= n; ++i) {
    acc += square(i);
  }
  return acc;
}

int main() {
  return sum_squares(3) == 14 ? 0 : 1;
}
