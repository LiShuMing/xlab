/**
 * 李超线段树（Li Chao Segment Tree）
 *
 * 解决的问题：动态插入一堆直线 y = kx + b，然后反复查询「在某个 x 处，所有直线里的最小值」。
 *   插入 O(log n)，查询 O(log n)，而且比「维护凸包」好写太多。
 *
 * 核心直觉：线段树的每个节点都「挂一条直线」，这条直线负责它所覆盖的整段 x 区间。
 *   插入新直线 f 时，在当前节点的区间中点 mid 处比较 f 与节点上已有的老直线 g：
 *     - 谁在 mid 处更优，谁就留在这个节点（它在中点赢，就大概率还负责这片区间）；
 *     - 输的那条往下递归，因为它只可能在区间的某一半里反超。
 *   两条直线最多相交一次，所以「谁更优」只会翻转一次 —— 这就是只需要往一侧递归的原因。
 *
 *   查询时从根一路走到底，把路径上每条线在该 x 处的值取最小即可。
 *
 * 为什么对查询引擎有用：
 *   优化器的代价模型里，很多代价函数是分段线性的（比如「每多读一千万行，多花 X 秒」）。
 *   当你要回答「用哪个并行度/哪种执行方式最便宜」时，本质就是「一组线性函数在某点取最小值」。
 *
 * 复杂度：插入 O(log n)，单点查询 O(log n)，空间 O(n)（x 的定义域大小）。
 */

#include "../include/fwd.h"

class LiChaoTree {
public:
    // 定义域：整数 x ∈ [xMin, xMax]
    LiChaoTree(int xMin, int xMax) : xMin_(xMin), xMax_(xMax) {
        int n = xMax - xMin + 1;
        tree_.assign(4 * n, Line{});  // 空节点挂一条「恒为 +INF」的线，等价于没有线
    }

    // 插入直线 y = kx + b
    void addLine(double k, double b) { addLine(Line{k, b}, 1, xMin_, xMax_); }

    // 查询所有已插入直线在 x 处的最小值
    double queryMin(int x) const { return queryMin(1, xMin_, xMax_, x); }

private:
    static constexpr double kInf = 1e18;

    struct Line {
        double k = 0.0;
        double b = kInf;  // 默认 b = +INF，表示「这条线不存在」

        double at(double x) const { return k * x + b; }
    };

    void addLine(Line line, int node, int l, int r) {
        int mid = (l + r) / 2;
        // 1. 谁在中点更优，谁就占据当前节点
        bool betterAtMid = line.at(mid) < tree_[node].at(mid);
        if (betterAtMid) swap(tree_[node], line);  // line 变成「输的那条」，继续往下送

        if (l == r) return;  // 叶子节点没有下一层了

        // 2. 输的那条只可能在某一半区间反超，判断是哪一半
        //    比较左端点：如果新线在左端点更优，说明它是在左半边反超的
        bool betterAtLeft = line.at(l) < tree_[node].at(l);
        if (betterAtLeft != betterAtMid) {
            addLine(line, node * 2, l, mid);  // 交点落在左半边
        } else {
            addLine(line, node * 2 + 1, mid + 1, r);  // 交点落在右半边
        }
    }

    double queryMin(int node, int l, int r, int x) const {
        double result = tree_[node].at(x);  // 当前节点这条线的贡献
        if (l == r) return result;
        int mid = (l + r) / 2;
        // 往 x 所在的子树走，路径上的每条线都要参与比较
        if (x <= mid) return min(result, queryMin(node * 2, l, mid, x));
        return min(result, queryMin(node * 2 + 1, mid + 1, r, x));
    }

    int xMin_;
    int xMax_;
    vector<Line> tree_;
};

int main() {
    const int kXMin = 1;
    const int kXMax = 10;
    LiChaoTree tree(kXMin, kXMax);

    // 三条直线：y = x + 2、y = -2x + 20、y = 0.5x + 6（水平方向代表不同代价模型）
    struct RawLine {
        double k;
        double b;
    };
    const vector<RawLine> lines = {{1.0, 2.0}, {-2.0, 20.0}, {0.5, 6.0}};
    for (const RawLine& line : lines) tree.addLine(line.k, line.b);

    cout << "[李超树] x -> 最小 y:" << endl;
    for (int x = kXMin; x <= kXMax; ++x) {
        double got = tree.queryMin(x);
        // 暴力对照：直接把三条线都算一遍取最小
        double expect = 1e18;
        for (const RawLine& line : lines) expect = min(expect, line.k * x + line.b);
        cout << "  x=" << x << "  min=" << got << "  (暴力=" << expect << ")" << endl;
        assert(fabs(got - expect) < 1e-9);
    }

    // 再插一条更低的线，之前的所有查询结果都应该跟着变低
    tree.addLine(0.0, -5.0);  // 常数线 y = -5
    assert(fabs(tree.queryMin(7) - (-5.0)) < 1e-9);
    cout << "[李超树] 加入 y = -5 后 x=7 的最小值 = " << tree.queryMin(7) << endl;

    cout << "algo_li_chao_tree: all checks passed" << endl;
    return 0;
}
