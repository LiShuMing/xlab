// 第二课：分支形态如何落到 IR。
//
// 看什么：
//   -O0：clamp 是三条 br 串起来的 CFG，每个 return 一个块；
//   -O2：clamp 通常被简化成 select 或几次 min/max 风格的比较，
//        simplifycfg 会把只有一条前驱的块合并掉；
//   count_even 里的 is_even 会被内联，循环里出现 and + icmp + br。

int clamp(int x, int lo, int hi) {
  if (x < lo) {
    return lo;
  }
  if (x > hi) {
    return hi;
  }
  return x;
}

static int is_even(int x) {
  return (x & 1) == 0;
}

int count_even(const int* a, int n) {
  int c = 0;
  for (int i = 0; i < n; ++i) {
    if (is_even(a[i])) {
      ++c;
    }
  }
  return c;
}

int main() {
  return clamp(5, 0, 3) == 3 && count_even(nullptr, 0) == 0 ? 0 : 1;
}
