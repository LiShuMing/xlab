/**
 * 线段树 Beats（Segment Tree Beats）—— 区间 chmin 与区间求和
 *
 * 解决的问题：支持三种操作
 *   - rangeChmin(l, r, x)：把区间内所有 a[i] 变成 min(a[i], x)
 *   - rangeSum(l, r)      ：区间和
 *   - rangeMax(l, r)      ：区间最大值
 *   普通的「区间修改」只有「整体加/整体赋值」才好做懒标记，
 *   因为 min(a[i], x) 对区间里每个元素的改动幅度不一样，没法用一个数描述。
 *
 * 核心直觉：光有「最大值」不够，还要多记一个「严格次大值」。
 *   每个节点维护四元组 (sum, max1, max2, cnt)：
 *     max1 = 区间最大值，max2 = 严格小于 max1 的最大值，cnt = max1 出现的次数
 *
 *   做 chmin(x) 时看 x 落在哪：
 *     - x >= max1            ：整个区间都不用改，直接返回；
 *     - max2 < x < max1      ：只有那 cnt 个最大值会被压成 x，其余不动！
 *                              于是能把「打标记」压缩成一步算术：
 *                                sum -= cnt * (max1 - x);  max1 = x;
 *     - x <= max2            ：影响范围搞不清了，只能老老实实递归下去。
 *
 *   为什么这样还是快？用一个「势能」来算：定义势能 = 每个节点 max1 与 max2 的差距种类数。
 *   每次递归到底都会让某个节点的 max1 和 max2 合并，势能减少；
 *   而每次只修改 O(log n) 个节点，势能总量 O(n log n)，所以均摊 O((n + q)·log n)。
 *   这套「势能分析法」值得单独吃透，它是分析递归暴力为什么快的标准工具。
 *
 * 数据库中的对应物：累积统计（running max / TopN 的上界收缩）、
 * 分段约束下的增量聚合。
 *
 * 复杂度：建树 O(n)，三种操作均摊 O(log n)，空间 O(n)。
 */

#include "../include/fwd.h"

class SegmentTreeBeats {
public:
    explicit SegmentTreeBeats(const vector<int>& a) : n_(static_cast<int>(a.size())) {
        tree_.assign(4 * max(1, n_), Node{});
        if (n_ > 0) build(1, 0, n_ - 1, a);
    }

    void rangeChmin(int l, int r, int x) {
        if (l > r || n_ == 0) return;
        rangeChmin(1, 0, n_ - 1, l, r, x);
    }

    long long rangeSum(int l, int r) {
        if (l > r || n_ == 0) return 0;
        return rangeSum(1, 0, n_ - 1, l, r);
    }

    int rangeMax(int l, int r) {
        if (l > r || n_ == 0) return kNoValue;
        return rangeMax(1, 0, n_ - 1, l, r);
    }

private:
    static constexpr int kNoValue = INT_MIN;  // 不存在次大值时的哨兵

    struct Node {
        long long sum = 0;      // 区间和
        int max1 = kNoValue;    // 最大值
        int max2 = kNoValue;    // 严格次大值（不存在则为 kNoValue）
        int cnt = 0;            // 最大值的出现次数
    };

    void build(int p, int l, int r, const vector<int>& a) {
        if (l == r) {
            tree_[p] = Node{a[l], a[l], kNoValue, 1};
            return;
        }
        int mid = (l + r) / 2;
        build(p * 2, l, mid, a);
        build(p * 2 + 1, mid + 1, r, a);
        pull(p);
    }

    // 由两个儿子重算父节点。合并规则：看谁的最大值更大
    void pull(int p) {
        Node& cur = tree_[p];
        const Node& lc = tree_[p * 2];
        const Node& rc = tree_[p * 2 + 1];
        cur.sum = lc.sum + rc.sum;
        if (lc.max1 == rc.max1) {
            cur.max1 = lc.max1;
            cur.cnt = lc.cnt + rc.cnt;              // 最大值左右都有，出现次数相加
            cur.max2 = max(lc.max2, rc.max2);       // 次大值取两边次大值的较大者
        } else if (lc.max1 > rc.max1) {
            cur.max1 = lc.max1;
            cur.cnt = lc.cnt;
            cur.max2 = max(lc.max2, rc.max1);       // 右边的最大值晋升为次大值候选
        } else {
            cur.max1 = rc.max1;
            cur.cnt = rc.cnt;
            cur.max2 = max(rc.max2, lc.max1);
        }
    }

    // 前提：max2 < x < max1。把区间里所有 max1 压成 x
    void applyChmin(int p, int x) {
        tree_[p].sum -= 1LL * tree_[p].cnt * (tree_[p].max1 - x);
        tree_[p].max1 = x;  // max2 不变，因为 x 严格大于 max2
    }

    // 下放懒标记：父节点的 max1 变低了，所有「最大值比它大」的儿子都要同步压低
    void pushdown(int p) {
        int limit = tree_[p].max1;
        if (tree_[p * 2].max1 > limit) applyChmin(p * 2, limit);
        if (tree_[p * 2 + 1].max1 > limit) applyChmin(p * 2 + 1, limit);
    }

    void rangeChmin(int p, int l, int r, int ql, int qr, int x) {
        if (qr < l || r < ql) return;         // 完全不相交
        if (tree_[p].max1 <= x) return;       // 整个区间都不需要改（包含 x >= max1 的情况）
        if (ql <= l && r <= qr && tree_[p].max2 < x) {
            applyChmin(p, x);                 // 只有最大值受影响，一步打完标记
            return;
        }
        // 剩下的情况：影响范围说不清，往下递归
        pushdown(p);
        int mid = (l + r) / 2;
        rangeChmin(p * 2, l, mid, ql, qr, x);
        rangeChmin(p * 2 + 1, mid + 1, r, ql, qr, x);
        pull(p);
    }

    long long rangeSum(int p, int l, int r, int ql, int qr) {
        if (qr < l || r < ql) return 0;
        if (ql <= l && r <= qr) return tree_[p].sum;
        pushdown(p);  // 查询前也要把标记下放，否则子节点的 sum 是旧的
        int mid = (l + r) / 2;
        return rangeSum(p * 2, l, mid, ql, qr) + rangeSum(p * 2 + 1, mid + 1, r, ql, qr);
    }

    int rangeMax(int p, int l, int r, int ql, int qr) {
        if (qr < l || r < ql) return kNoValue;
        if (ql <= l && r <= qr) return tree_[p].max1;
        pushdown(p);
        int mid = (l + r) / 2;
        return max(rangeMax(p * 2, l, mid, ql, qr), rangeMax(p * 2 + 1, mid + 1, r, ql, qr));
    }

    vector<Node> tree_;
    int n_;
};

// 极小的确定性伪随机数发生器，保证每次运行结果一样
struct Lcg {
    unsigned state = 12345u;

    int next(int lo, int hi) {
        state = state * 1103515245u + 12345u;
        return lo + static_cast<int>((state >> 16) % static_cast<unsigned>(hi - lo + 1));
    }
};

int main() {
    vector<int> a = {1, 5, 3, 7, 9};
    SegmentTreeBeats st(a);
    cout << "[Beats] 初始数组: ";
    printVector(a);

    st.rangeChmin(0, 2, 4);  // 前三个元素 1,5,3 与 4 取 min => 1,4,3
    cout << "[Beats] chmin([0,2], 4) 后区间和 = " << st.rangeSum(0, 4)
         << "，最大值 = " << st.rangeMax(0, 4) << endl;
    assert(st.rangeSum(0, 4) == 1 + 4 + 3 + 7 + 9);
    assert(st.rangeMax(0, 4) == 9);
    assert(st.rangeSum(0, 2) == 8);

    // 随机对拍：200 次 chmin，每次都用暴力数组核对区间和与最大值
    Lcg rng;
    const int n = 60;
    const int ops = 200;
    vector<int> brute(n);
    for (int i = 0; i < n; ++i) brute[i] = rng.next(-20, 20);
    SegmentTreeBeats stress(brute);

    for (int round = 0; round < ops; ++round) {
        int l = rng.next(0, n - 1);
        int r = rng.next(0, n - 1);
        if (l > r) swap(l, r);
        int x = rng.next(-30, 30);

        stress.rangeChmin(l, r, x);
        for (int i = l; i <= r; ++i) brute[i] = min(brute[i], x);

        assert(stress.rangeSum(l, r) == accumulate(brute.begin() + l, brute.begin() + r + 1, 0LL));
    }

    long long total = accumulate(brute.begin(), brute.end(), 0LL);
    int overallMax = *max_element(brute.begin(), brute.end());
    cout << "[Beats] 对拍 " << ops << " 次 chmin 后：区间和 = " << stress.rangeSum(0, n - 1)
         << "（暴力 = " << total << "），最大值 = " << stress.rangeMax(0, n - 1)
         << "（暴力 = " << overallMax << "）" << endl;
    assert(stress.rangeSum(0, n - 1) == total);
    assert(stress.rangeMax(0, n - 1) == overallMax);

    cout << "algo_segment_tree_beats: all checks passed" << endl;
    return 0;
}
