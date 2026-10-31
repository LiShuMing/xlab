/**
 * 树状数组（Fenwick Tree / Binary Indexed Tree, BIT）
 *
 * 解决的问题：单点修改 + 前缀和查询，两个操作都是 O(log n)，
 * 但常数比线段树小一半以上（不用递归，不用 4n 空间，只要 n+1）。
 *
 * 核心直觉：lowbit(x) = x & -x，取出 x 的二进制里最低位的 1。
 *   把下标 i 想象成「负责区间 (i - lowbit(i), i] 的和」，
 *   查询时反复减去 lowbit，修改时反复加上 lowbit，两条路径都是 O(log n)：
 *     6  = 110 -> 4 -> 0           （查询：6 负责 [5,6]，4 负责 [1,4]）
 *     5  = 101 -> 6 -> 8 -> 16 ... （修改：一路向上通知所有祖先）
 *
 * 为什么工程上值得用：
 *   - 树状数组 ↔ 线段树是「同一问题的两种代价分配」，比较两者常数差异很能说明
 *     「缓存局部性 + 少一次递归」在真实硬件上值多少钱；
 *   - 用它维护前缀聚合，是增量视图（IVM）/ 滑动统计的最小原语。
 *
 * 复杂度：单点修改 O(log n)，前缀和 O(log n)，空间 O(n)（下标从 1 开始）。
 */

#include "../include/fwd.h"

class Fenwick {
public:
    explicit Fenwick(int n) : tree_(n + 1, 0) {}

    // O(n log n) 建树：等价于逐个 add，最直观
    explicit Fenwick(const vector<int>& a) : tree_(a.size() + 1, 0) {
        for (int i = 0; i < static_cast<int>(a.size()); ++i) add(i, a[i]);
    }

    // O(n) 线性建树：tree[i] 先存 a[i-1]，再把整块「向上贡献」给父节点
    static Fenwick buildLinear(const vector<int>& a) {
        Fenwick fw(static_cast<int>(a.size()));
        for (int i = 1; i <= static_cast<int>(a.size()); ++i) {
            fw.tree_[i] += a[i - 1];
            int parent = i + lowbit(i);  // i 的贡献要合并进它的父节点
            if (parent <= static_cast<int>(a.size())) fw.tree_[parent] += fw.tree_[i];
        }
        return fw;
    }

    // 单点修改：a[idx] += delta（idx 是 0 基下标，对外友好；内部转成 1 基）
    void add(int idx, int delta) {
        for (int i = idx + 1; i < static_cast<int>(tree_.size()); i += lowbit(i)) tree_[i] += delta;
    }

    // 前缀和：[0, idx]
    long long prefixSum(int idx) const {
        long long sum = 0;
        for (int i = idx + 1; i > 0; i -= lowbit(i)) sum += tree_[i];
        return sum;
    }

    // 区间和：[l, r]，两次前缀和相减
    long long rangeSum(int l, int r) const { return prefixSum(r) - prefixSum(l - 1); }

private:
    static int lowbit(int x) { return x & -x; }  // 最低位的 1，负数用补码表示

    vector<long long> tree_;
};

int main() {
    const vector<int> a = {3, 1, 4, 1, 5, 9, 2, 6};
    Fenwick fw(a);

    cout << "[树状数组] 原数组: ";
    printVector(a);
    cout << "[树状数组] 前缀和 [0..7]: ";
    for (int i = 0; i < static_cast<int>(a.size()); ++i) cout << fw.prefixSum(i) << " ";
    cout << endl;

    // 前三个值 3+1+4 = 8
    cout << "[树状数组] rangeSum(0,2) = " << fw.rangeSum(0, 2) << endl;
    assert(fw.rangeSum(0, 2) == 8);

    // 暴力对照：所有区间和都必须和逐项累加一致
    for (int l = 0; l < static_cast<int>(a.size()); ++l) {
        long long expect = 0;
        for (int r = l; r < static_cast<int>(a.size()); ++r) {
            expect += a[r];
            assert(fw.rangeSum(l, r) == expect);
        }
    }

    // 单点修改后必须同步正确：a[3] 从 1 改成 100，总和增加 99
    fw.add(3, 99);
    cout << "[树状数组] a[3] += 99 后总和 = " << fw.rangeSum(0, 7) << endl;
    assert(fw.rangeSum(0, 7) == 31 + 99);

    // O(n) 与 O(n log n) 两种建树方式结果必须完全一致
    Fenwick fast = Fenwick::buildLinear(a);
    for (int i = 0; i < static_cast<int>(a.size()); ++i) assert(fast.prefixSum(i) == fw.prefixSum(i) - (i >= 3 ? 99 : 0));

    cout << "algo_fenwick: all checks passed" << endl;
    return 0;
}
