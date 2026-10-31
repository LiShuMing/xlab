/**
 * 线段树合并 & 分裂（Segment Tree Merge / Split）
 *
 * 解决的问题：同时管理很多个「有序多重集合」，并且要频繁做两件事：
 *   - merge(a, b)：把集合 b 的所有元素倒进集合 a；
 *   - split(root, k)：把一个集合按顺序切成「前 k 个」和「剩余部分」。
 *   如果用普通数据结构，一次合并要 O(size) 逐个搬运；用动态开点的权值线段树可以做到
 *   「只合并两边都非空的节点」，均摊 O(合并后总节点数)。
 *
 * 核心直觉：
 *   1. 动态开点：值域是 [1, maxValue]，但不是每个值都出现，所以节点在用到时才创建；
 *      一开始在一棵树上插 3 个数，只有 O(log V) 个节点，不是 O(V)。
 *   2. 合并：两棵树的下标体系完全一致（同一个值域、同样的分裂方式），
 *      于是可以把 b 的节点直接「接到」a 上：a 没有孩子就整枝搬过来，两边都有就递归。
 *      —— 一次合并的总代价正比于「真正发生重叠的节点数」，而不是值域大小。
 *   3. 分裂：按左子树的元素个数 k 判断切口落在左半边还是右半边，
 *      被切开的那一层需要新建一对节点，其余子树整枝摘走。
 *
 *   注意本文件的实现是「破坏性」的：merge 之后 b 不可再用（它的节点已被 a 接管），
 *   split 之后原来的根也不再可用。教学版不回收废弃节点，真实实现会走内存池 + 空闲链表。
 *
 * 数据库中的对应物：
 *   - 分区 / 分桶的合并与拆分：把两个有序 Segment 归并成一个，或把一个 RowSet 按 key 切成两半；
 *   - LSM 的 compaction、小文件合并（本质就是「相同 key 域的树合并」）；
 *   - 增量视图维护里，把两批 delta 聚合到同一个键空间上。
 *
 * 复杂度：插入 O(log V)；合并均摊 O(重叠节点数)；按元素个数分裂 O(log V)；
 *   空间 O(元素个数 · log V)。
 */

#include "../include/fwd.h"

class DynamicSegmentTree {
public:
    // 值域固定为 [1, maxValue]
    explicit DynamicSegmentTree(int maxValue) : maxValue_(maxValue) {
        nodes_.push_back(Node{});  // 0 号是空节点，省掉所有判空分支
    }

    // 往集合里插入一个 value（delta = -1 就是删除）
    int insert(int root, int value, int delta = 1) {
        return insert(root, 1, maxValue_, value, delta);
    }

    // 把 b 的所有元素合并进 a，返回新的根；此后 b 作废
    int merge(int a, int b) {
        if (a == 0) return b;  // a 这边是空的，整枝搬过去
        if (b == 0) return a;  // b 这边是空的，什么都不用做
        // 两边都有节点：孩子递归合并，计数相加
        nodes_[a].lc = merge(nodes_[a].lc, nodes_[b].lc);
        nodes_[a].rc = merge(nodes_[a].rc, nodes_[b].rc);
        nodes_[a].sum += nodes_[b].sum;
        return a;
    }

    // 把 root 拆成两个：x = 最小的 k 个元素，y = 剩下的
    void split(int root, int k, int& x, int& y) {
        x = 0;
        y = 0;
        if (root == 0) return;
        if (k <= 0) {  // 一个都不留在左边
            y = root;
            return;
        }
        if (k >= nodes_[root].sum) {  // 全部留在左边
            x = root;
            return;
        }

        int lc = nodes_[root].lc;
        int rc = nodes_[root].rc;
        int leftSum = sumOf(lc);

        if (k <= leftSum) {
            // 切口在左子树内部：左子树再拆，右子树整块归 y
            int a = 0;
            int b = 0;
            split(lc, k, a, b);
            int sumA = sumOf(a);
            int sumB = sumOf(b);
            int sumRc = sumOf(rc);
            x = newNode();
            nodes_[x].lc = a;
            nodes_[x].sum = sumA;
            y = newNode();
            nodes_[y].lc = b;
            nodes_[y].rc = rc;
            nodes_[y].sum = sumB + sumRc;
        } else {
            // 切口在右子树内部：左子树整块归 x，右子树再拆
            int a = 0;
            int b = 0;
            split(rc, k - leftSum, a, b);
            int sumA = sumOf(a);
            int sumB = sumOf(b);
            x = newNode();
            nodes_[x].lc = lc;
            nodes_[x].rc = a;
            nodes_[x].sum = leftSum + sumA;
            y = newNode();
            nodes_[y].rc = b;
            nodes_[y].sum = sumB;
        }
    }

    int total(int root) const { return nodes_[root].sum; }

    // 第 k 小（k 从 1 开始）
    int kth(int root, int k) const {
        int l = 1;
        int r = maxValue_;
        int p = root;
        while (l < r) {
            int mid = (l + r) / 2;
            int leftSum = sumOf(nodes_[p].lc);
            if (k <= leftSum) {
                p = nodes_[p].lc;  // 第 k 小在左半边
                r = mid;
            } else {
                k -= leftSum;  // 扣掉左半边，去右半边找第 (k - leftSum) 小
                p = nodes_[p].rc;
                l = mid + 1;
            }
        }
        return l;
    }

    // 升序导出所有元素（用于和暴力结果对拍）
    vector<int> values(int root) const {
        vector<int> out;
        collect(root, 1, maxValue_, out);
        return out;
    }

    int nodeCount() const { return static_cast<int>(nodes_.size()); }

private:
    struct Node {
        int lc = 0;   // 左孩子下标（0 = 空）
        int rc = 0;   // 右孩子下标（0 = 空）
        int sum = 0;  // 该值域区间内的元素个数
    };

    int sumOf(int idx) const { return nodes_[idx].sum; }  // 0 号节点 sum 恒为 0

    int newNode() {
        nodes_.push_back(Node{});
        return static_cast<int>(nodes_.size()) - 1;
    }

    int insert(int p, int l, int r, int value, int delta) {
        if (p == 0) p = newNode();  // 动态开点：走到才创建
        nodes_[p].sum += delta;
        if (l == r) return p;
        int mid = (l + r) / 2;
        if (value <= mid) {
            nodes_[p].lc = insert(nodes_[p].lc, l, mid, value, delta);
        } else {
            nodes_[p].rc = insert(nodes_[p].rc, mid + 1, r, value, delta);
        }
        return p;
    }

    void collect(int p, int l, int r, vector<int>& out) const {
        if (p == 0) return;
        if (l == r) {
            for (int i = 0; i < nodes_[p].sum; ++i) out.push_back(l);  // 重复元素按次数展开
            return;
        }
        int mid = (l + r) / 2;
        collect(nodes_[p].lc, l, mid, out);
        collect(nodes_[p].rc, mid + 1, r, out);
    }

    vector<Node> nodes_;
    int maxValue_;
};

int main() {
    DynamicSegmentTree tree(10);  // 值域 [1, 10]

    // 两个「分片」，各自是一个有序多重集合
    int shardA = 0;
    for (int v : {1, 3, 5}) shardA = tree.insert(shardA, v);
    int shardB = 0;
    for (int v : {2, 4}) shardB = tree.insert(shardB, v);

    cout << "[合并分裂] 分片 A: ";
    printVector(tree.values(shardA));
    cout << "[合并分裂] 分片 B: ";
    printVector(tree.values(shardB));

    // ---- 合并：等价于把两个有序 Segment 归并成一个 ----
    int merged = tree.merge(shardA, shardB);
    cout << "[合并分裂] 合并后: ";
    printVector(tree.values(merged));
    assert((tree.values(merged) == vector<int>{1, 2, 3, 4, 5}));
    assert(tree.total(merged) == 5);
    assert(tree.kth(merged, 1) == 1);
    assert(tree.kth(merged, 3) == 3);
    assert(tree.kth(merged, 5) == 5);

    // ---- 分裂：前 2 个一组，后 3 个一组 ----
    int left = 0;
    int right = 0;
    tree.split(merged, 2, left, right);
    cout << "[合并分裂] split(2) 左侧: ";
    printVector(tree.values(left));
    cout << "[合并分裂] split(2) 右侧: ";
    printVector(tree.values(right));

    assert((tree.values(left) == vector<int>{1, 2}));
    assert((tree.values(right) == vector<int>{3, 4, 5}));
    assert(tree.total(left) == 2);
    assert(tree.total(right) == 3);

    // 再分裂一次：验证「切在同一个位置」和「切到边界」两种退化情况
    int head = 0;
    int tail = 0;
    tree.split(left, 0, head, tail);
    assert(tree.total(head) == 0);  // 切 0 个，左侧为空
    assert(tree.total(tail) == 2);

    cout << "[合并分裂] 节点池大小 = " << tree.nodeCount() << endl;
    cout << "algo_segment_tree_merge_split: all checks passed" << endl;
    return 0;
}
