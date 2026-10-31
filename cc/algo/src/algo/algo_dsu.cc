/**
 * 并查集（Disjoint Set Union, DSU / Union-Find）
 *
 * 解决的问题：动态维护一堆「等价关系」，随时回答「这两个元素是否属于同一类」。
 * 只用支持两种操作，但都很快：
 *   - unite(a, b)：把 a 和 b 所在的类合并
 *   - find(a)    ：返回 a 所在类的代表元（同一类的代表元必然相同）
 *
 * 两个关键优化，缺一不可：
 *   1. 路径减半（path halving）：find 走到一半时顺手把节点挂到祖父上，树被压得很扁；
 *      相比递归式的「路径压缩」，它不需要递归栈，且同样能拿到均摊复杂度。
 *   2. 按大小合并（union by size）：永远把小的树挂到大的树下面，避免长出长链。
 *
 * 两者合用的均摊复杂度是 O(alpha(n))，alpha 是反阿克曼函数。
 * 实际上 n < 2^65536 时 alpha(n) <= 4，工程上可以直接当 O(1) 看。
 *
 * 数据库中的对应物：
 *   - 优化器的等价类（equivalence class）合并：a=b、b=c 推出 a=b=c，
 *     于是谓词 col_a = col_c 可以判定为恒真而被剪掉，这是谓词推导/常量传播的基础；
 *   - join 重排时判断两张表是否已被同一组等值条件连在一起（连通分量就是 join 图的连通块）；
 *   - 分区裁剪里判断某个分片是否还可能需要参与 shuffle。
 *
 * 复杂度：build O(n)，find/unite 均摊 O(alpha(n))，空间 O(n)。
 */

#include "../include/fwd.h"

class DisjointSet {
public:
    explicit DisjointSet(int n) : parent_(n), size_(n, 1), groups_(n) {
        // 初始时每个元素自成一类，父节点就是自己
        iota(parent_.begin(), parent_.end(), 0);
    }

    // 返回 x 所在类的代表元
    int find(int x) {
        while (parent_[x] != x) {
            parent_[x] = parent_[parent_[x]];  // 路径减半：跳到祖父，路径长度立刻缩短一半
            x = parent_[x];
        }
        return x;
    }

    // 合并 a、b 所在的类；本来就在同一类时返回 false（不重复计数）
    bool unite(int a, int b) {
        a = find(a);
        b = find(b);
        if (a == b) return false;
        if (size_[a] < size_[b]) swap(a, b);  // 小树挂到大树下，保证树高 O(log n)
        parent_[b] = a;
        size_[a] += size_[b];
        --groups_;
        return true;
    }

    bool connected(int a, int b) { return find(a) == find(b); }

    int groupSize(int x) { return size_[find(x)]; }

    int groupCount() const { return groups_; }

private:
    vector<int> parent_;  // parent_[i]：i 的父节点，根节点指向自己
    vector<int> size_;    // size_[i]：仅当 i 是根时有效，表示该类的元素个数
    int groups_;          // 当前还剩多少个类
};

// ---------------------------------------------------------------------------
// 演示一：连通性维护
// ---------------------------------------------------------------------------
static void demoConnectivity() {
    // 0-1、2-3、1-2 依次合并后，{0,1,2,3} 成一类，4 和 5 各自独立
    DisjointSet dsu(6);
    dsu.unite(0, 1);
    dsu.unite(2, 3);
    dsu.unite(1, 2);

    cout << "[连通性] 0 与 3 连通: " << (dsu.connected(0, 3) ? "是" : "否") << endl;
    cout << "[连通性] 0 与 4 连通: " << (dsu.connected(0, 4) ? "是" : "否") << endl;
    cout << "[连通性] 0 所在类大小: " << dsu.groupSize(0) << endl;
    cout << "[连通性] 当前类个数: " << dsu.groupCount() << endl;

    assert(dsu.connected(0, 3));
    assert(!dsu.connected(0, 4));
    assert(dsu.groupSize(3) == 4);
    assert(dsu.groupCount() == 3);  // {0,1,2,3}、{4}、{5}

    // 重复合并同一个类不会重复计数
    assert(!dsu.unite(1, 2));
    assert(dsu.groupCount() == 3);
}

// ---------------------------------------------------------------------------
// 演示二：优化器里的等价类合并（谓词推导）
// ---------------------------------------------------------------------------
static void demoEquivalenceClass() {
    // 用 0..4 代指 5 个列，join/过滤条件如下：
    //   t1.a = t2.b, t2.b = t3.c, t4.d = t5.e
    DisjointSet classes(5);
    classes.unite(0, 1);  // a = b
    classes.unite(1, 2);  // b = c
    classes.unite(3, 4);  // d = e

    bool implied = classes.connected(0, 2);  // a = c 能否被推出？
    bool notImplied = classes.connected(0, 3);
    cout << "[等价类] a = c 可推出: " << (implied ? "是" : "否") << endl;
    cout << "[等价类] a = d 可推出: " << (notImplied ? "是" : "否") << endl;

    assert(implied);      // a、b、c 同属一个等价类 => 谓词 a=c 恒真
    assert(!notImplied);  // a 与 d 无关 => 谓词不能删
}

int main() {
    demoConnectivity();
    demoEquivalenceClass();
    cout << "algo_dsu: all checks passed" << endl;
    return 0;
}
