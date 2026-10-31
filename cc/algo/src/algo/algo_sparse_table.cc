/**
 * ST 表（Sparse Table）
 *
 * 解决的问题：静态数组（没有修改）的区间最值查询 RMQ，预处理 O(n log n)，查询 O(1)。
 *
 * 核心直觉：倍增 + 空间换时间。
 *   st[k][i] 表示「从 i 开始、长度为 2^k 的区间」的最值。
 *   递推关系一眼可见：长度为 2^k 的区间 = 左右两个长度 2^(k-1) 的区间拼起来，
 *     st[k][i] = min(st[k-1][i], st[k-1][i + 2^(k-1)])
 *
 *   查询 [l, r] 时取 k = floor(log2(r-l+1))，用两块「长度 2^k、可以重叠」的区间覆盖：
 *     min( st[k][l], st[k][r - 2^k + 1] )
 *   两块长度各 2^k >= 区间长度的一半，所以一定能盖满，重叠部分对 min 无影响。
 *
 * ★ 为什么 sum 不能用 ST 表，而 min/max/gcd 可以？
 *   因为 ST 表查询依赖「重叠的部分重复计算不会改变答案」，这类运算叫幂等（idempotent）。
 *   sum 不幂等（重叠的段会被加两次），所以区间和只能靠线段树/树状数组。
 *   这个区别就是「RMQ 类问题」和「聚合类问题」的分水岭。
 *
 * 数据库中的对应物：列存块级 min/max 索引、字典编码的静态查找表、
 * 以及任何「预计算一次、查询无数次」的读多写少场景。
 *
 * 复杂度：预处理 O(n log n)，单次查询 O(1)，空间 O(n log n)。
 */

#include "../include/fwd.h"

class SparseTable {
public:
    explicit SparseTable(const vector<int>& a) : a_(a) {
        int n = static_cast<int>(a.size());
        // lg[i] = floor(log2(i))，用递推算，避免浮点误差
        lg_.assign(n + 1, 0);
        for (int i = 2; i <= n; ++i) lg_[i] = lg_[i / 2] + 1;

        int levels = (n == 0) ? 1 : lg_[n] + 1;
        st_.assign(levels, vector<int>(n));
        st_[0] = a;  // 长度 1 的区间就是元素本身

        for (int k = 1; k < levels; ++k) {
            int half = 1 << (k - 1);
            for (int i = 0; i + (1 << k) <= n; ++i) {
                st_[k][i] = min(st_[k - 1][i], st_[k - 1][i + half]);
            }
        }
    }

    // 闭区间 [l, r] 的最小值
    int rangeMin(int l, int r) const {
        int k = lg_[r - l + 1];
        int len = 1 << k;
        return min(st_[k][l], st_[k][r - len + 1]);  // 两块允许重叠
    }

private:
    vector<int> a_;
    vector<int> lg_;             // lg_[len] = floor(log2(len))
    vector<vector<int>> st_;     // st_[k][i]
};

int main() {
    const vector<int> a = {5, 3, 8, 1, 9, 2, 7, 4, 6, 0};
    SparseTable st(a);

    cout << "[ST 表] 原数组: ";
    printVector(a);
    cout << "[ST 表] [1,4] 最小值 = " << st.rangeMin(1, 4) << endl;  // min(3,8,1,9) = 1
    cout << "[ST 表] [6,9] 最小值 = " << st.rangeMin(6, 9) << endl;  // min(7,4,6,0) = 0
    assert(st.rangeMin(1, 4) == 1);
    assert(st.rangeMin(6, 9) == 0);

    // 暴力对照：所有区间都必须正确，含长度为 1 和整个数组的边界情况
    for (int l = 0; l < static_cast<int>(a.size()); ++l) {
        int expect = a[l];
        for (int r = l; r < static_cast<int>(a.size()); ++r) {
            expect = min(expect, a[r]);
            assert(st.rangeMin(l, r) == expect);
        }
    }

    cout << "algo_sparse_table: all checks passed" << endl;
    return 0;
}
