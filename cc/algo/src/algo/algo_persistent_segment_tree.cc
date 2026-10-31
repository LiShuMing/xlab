/**
 * 可持久化线段树（Persistent Segment Tree）
 *
 * 解决的问题：数据结构会被不断修改，但「历史版本」必须能随时查回来。
 *   朴素做法是每次修改都整棵拷贝一份，O(n) 空间，改 q 次就是 O(nq)。
 *   可持久化线段树用「路径复制」把它降到每次 O(log n)。
 *
 * 核心直觉：一次单点修改，只影响从根到叶子的一条路径上的 O(log n) 个节点。
 *   所以只把这条路径上的节点复制一份新的，新节点指向「没被修改的旧子树」——
 *   新旧两棵树共享了绝大部分节点，既省空间，又天然保证了「旧版本永远不会被改坏」。
 *
 *       旧版本根                   新版本根
 *         /     \                    /    \
 *      [A]      [B]   ==>       [A']      [B]     <- A 被复制成 A'，B 原样共享
 *      / \      / \              /  \      / \
 *    ...  ...  ... ...         ...  ...  ... ...
 *
 *   这就是「不可变数据结构（immutable / copy-on-write）」最典型的样子。
 *
 * 数据库中的对应物：
 *   - MVCC 的版本链 / 快照读：事务看到的是某个时间点的「版本根」，后续写入只改自己的新版本；
 *   - 时态表（temporal table）的 as-of join、闪回查询（flashback query）；
 *   - LSM 里 SST 不可变 + 后台合并，也是同一种「只追加、不改旧」的思路。
 *
 * 复杂度：建树 O(n)，单次修改 O(log n) 个新节点，区间查询 O(log n)，
 *   总空间 O(n + q·log n)，q 为修改次数。
 */

#include "../include/fwd.h"

class PersistentSegmentTree {
public:
    explicit PersistentSegmentTree(const vector<int>& a) : n_(static_cast<int>(a.size())) {
        nodes_.reserve(2 * 4 * n_ + 1);
        nodes_.push_back(Node{});  // 0 号是「空节点」，省掉所有判空分支
        roots_.push_back(build(0, n_ - 1, a));
    }

    // 在第 version 版的基础上把 a[idx] 改成 val，返回新版本号（旧版本不变）
    int update(int version, int idx, int val) {
        roots_.push_back(update(roots_[version], 0, n_ - 1, idx, val));
        return static_cast<int>(roots_.size()) - 1;
    }

    long long rangeSum(int version, int l, int r) const {
        return rangeSum(roots_[version], 0, n_ - 1, l, r);
    }

    int versionCount() const { return static_cast<int>(roots_.size()); }
    int nodeCount() const { return static_cast<int>(nodes_.size()); }

private:
    struct Node {
        int left = 0;      // 0 表示空节点
        int right = 0;
        long long sum = 0;
    };

    int newNode(const Node& proto) {
        nodes_.push_back(proto);
        return static_cast<int>(nodes_.size()) - 1;
    }

    int build(int l, int r, const vector<int>& a) {
        int cur = newNode(Node{});
        if (l == r) {
            nodes_[cur].sum = a[l];
            return cur;
        }
        int mid = (l + r) / 2;
        nodes_[cur].left = build(l, mid, a);
        nodes_[cur].right = build(mid + 1, r, a);
        nodes_[cur].sum = nodes_[nodes_[cur].left].sum + nodes_[nodes_[cur].right].sum;
        return cur;
    }

    int update(int prev, int l, int r, int idx, int val) {
        // 第一步：把旧节点整份复制出来（路径复制）。后续只改这份拷贝，旧节点纹丝不动
        int cur = newNode(nodes_[prev]);
        if (l == r) {
            nodes_[cur].sum = val;
            return cur;
        }
        int mid = (l + r) / 2;
        // 只有目标所在的那一侧需要新建节点，另一侧继续共享旧版本的子树
        if (idx <= mid) {
            nodes_[cur].left = update(nodes_[prev].left, l, mid, idx, val);
        } else {
            nodes_[cur].right = update(nodes_[prev].right, mid + 1, r, idx, val);
        }
        nodes_[cur].sum = nodes_[nodes_[cur].left].sum + nodes_[nodes_[cur].right].sum;
        return cur;
    }

    long long rangeSum(int node, int l, int r, int ql, int qr) const {
        if (node == 0 || qr < l || r < ql) return 0;  // 空节点或完全不相交
        if (ql <= l && r <= qr) return nodes_[node].sum;
        int mid = (l + r) / 2;
        return rangeSum(nodes_[node].left, l, mid, ql, qr) +
               rangeSum(nodes_[node].right, mid + 1, r, ql, qr);
    }

    vector<Node> nodes_;  // 节点池：所有版本共享一池节点，只追加不回收
    vector<int> roots_;   // 每个版本的根节点下标
    int n_;
};

int main() {
    const vector<int> a = {1, 2, 3, 4, 5};
    PersistentSegmentTree pst(a);
    cout << "[可持久化] 初始数组: ";
    printVector(a);

    int v0 = 0;
    int v1 = pst.update(v0, 2, 10);  // 版本 1：{1, 2, 10, 4, 5}
    int v2 = pst.update(v1, 0, 100); // 版本 2：{100, 2, 10, 4, 5}

    cout << "[可持久化] v0 区间和 [0,4] = " << pst.rangeSum(v0, 0, 4) << endl;
    cout << "[可持久化] v1 区间和 [0,4] = " << pst.rangeSum(v1, 0, 4) << endl;
    cout << "[可持久化] v2 区间和 [0,4] = " << pst.rangeSum(v2, 0, 4) << endl;
    cout << "[可持久化] v1 子区间和 [0,2] = " << pst.rangeSum(v1, 0, 2) << endl;

    // 关键验证：新的修改不会污染旧版本
    assert(pst.rangeSum(v0, 0, 4) == 15);  // 1+2+3+4+5
    assert(pst.rangeSum(v1, 0, 4) == 22);  // 1+2+10+4+5
    assert(pst.rangeSum(v2, 0, 4) == 121); // 100+2+10+4+5
    assert(pst.rangeSum(v0, 0, 2) == 6);
    assert(pst.rangeSum(v1, 0, 2) == 13);
    assert(pst.versionCount() == 3);

    // 共享结构的直接证据：3 个版本次修改 2 次，节点数远小于 3 棵独立线段树
    cout << "[可持久化] 节点总数 = " << pst.nodeCount() << "（3 棵独立线段树约为 "
         << 3 * (2 * 4 * 5) << " 个槽位）" << endl;
    assert(pst.nodeCount() < 3 * 2 * 5);

    cout << "algo_persistent_segment_tree: all checks passed" << endl;
    return 0;
}
