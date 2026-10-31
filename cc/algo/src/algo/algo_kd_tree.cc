/**
 * K-D Tree（k 维树）
 *
 * 解决的问题：二维/多维空间里的「矩形范围计数」和「最近邻查询」，
 * 不用把每个点都扫一遍 —— 靠包围盒剪枝，平均 O(log n + 命中数)。
 *
 * 核心直觉：把线段树的「按位置切」换成「按维度轮流切」。
 *   第 0 层用 x 的中位数把点集切成左右两半，第 1 层用 y 的中位数切，第 2 层再用 x……
 *   于是每个节点都能圈出一个「矩形包围盒」（bounding box），并且知道子树里有多少个点。
 *
 *   查询矩形 [x1,x2] × [y1,y2] 时，对每个节点做三选一判断：
 *     - 包围盒与查询框完全不相交 => 整棵子树剪掉，O(1) 结束；
 *     - 包围盒完全被查询框包住 => 整棵子树命中，直接加 cnt，O(1) 结束；
 *     - 部分相交 => 检查当前点，然后递归两个孩子。
 *   这就是「分区裁剪」的本质。
 *
 * 和空间填充曲线的关系：
 *   你已有的 algo_hilbert.cc / algo_zorder.cc 是「把二维压成一维，再用 B 树索引」；
 *   K-D Tree 是「保持树形，按维度轮流分区」。两者解决同一类问题，取舍不同：
 *   曲线编码对写入友好、能直接塞进现有索引；K-D Tree 的局部性更好、剪枝更精准。
 *
 * 数据库中的对应物：空间索引（GeoMesa/PostGIS 的 R 树亲戚）、
 * 多维统计信息的直方图分桶、点查/范围查的剪枝决策。
 *
 * 复杂度：建树 O(n log n)，矩形计数平均 O(sqrt(n) + 命中数)，最近邻平均 O(log n)。
 */

#include "../include/fwd.h"

struct KdPoint {
    double x = 0.0;
    double y = 0.0;
};

class KdTree {
public:
    explicit KdTree(vector<KdPoint> points) : pts_(std::move(points)) {
        nodes_.reserve(pts_.size());
        root_ = build(0, static_cast<int>(pts_.size()) - 1, 0);
    }

    // 统计落在矩形 [x1,x2] × [y1,y2] 内的点数
    int rangeCount(double x1, double x2, double y1, double y2) const {
        return rangeCount(root_, x1, x2, y1, y2);
    }

    // 距离查询点最近的点（欧氏距离的平方做比较，省掉开方）
    KdPoint nearest(double x, double y) const {
        KdPoint best;
        double bestDist = kInf;
        nearest(root_, KdPoint{x, y}, best, bestDist);
        return best;
    }

private:
    static constexpr double kInf = 1e300;

    struct Node {
        KdPoint point;
        int axis = 0;        // 该节点是按哪个维度切的：0 = x，1 = y
        int left = -1;       // -1 表示空
        int right = -1;
        int count = 0;       // 子树内的点数
        double minX = 0.0, maxX = 0.0, minY = 0.0, maxY = 0.0;  // 子树包围盒
    };

    // 递归建树：每一层按 axis 维取中位数切成两半
    int build(int lo, int hi, int depth) {
        if (lo > hi) return -1;
        int mid = (lo + hi) / 2;
        int axis = depth % 2;  // 轮流按 x、y 切

        // nth_element 保证 pts_[mid] 就是这一维的中位数，且左边都比它小、右边都比它大
        // 平均 O(n)，整体建树 O(n log n)；比每层都 sort 一遍省一半以上
        nth_element(pts_.begin() + lo, pts_.begin() + mid, pts_.begin() + hi + 1,
                    [axis](const KdPoint& a, const KdPoint& b) {
                        return axis == 0 ? a.x < b.x : a.y < b.y;
                    });

        Node node;
        node.point = pts_[mid];
        node.axis = axis;
        node.count = hi - lo + 1;
        node.left = build(lo, mid - 1, depth + 1);
        node.right = build(mid + 1, hi, depth + 1);

        // 包围盒 = 自己和两个孩子的包围盒的并
        node.minX = node.maxX = node.point.x;
        node.minY = node.maxY = node.point.y;
        expandBox(node, node.left);
        expandBox(node, node.right);

        nodes_.push_back(node);
        return static_cast<int>(nodes_.size()) - 1;
    }

    void expandBox(Node& node, int child) const {
        if (child < 0) return;
        const Node& c = nodes_[child];
        node.minX = min(node.minX, c.minX);
        node.maxX = max(node.maxX, c.maxX);
        node.minY = min(node.minY, c.minY);
        node.maxY = max(node.maxY, c.maxY);
    }

    int rangeCount(int idx, double x1, double x2, double y1, double y2) const {
        if (idx < 0) return 0;
        const Node& node = nodes_[idx];

        // 情况 1：包围盒与查询框完全不相交 => 整棵子树剪掉
        if (node.maxX < x1 || node.minX > x2 || node.maxY < y1 || node.minY > y2) return 0;

        // 情况 2：包围盒完全落在查询框内 => 整棵子树全部命中，不必再往下走
        if (x1 <= node.minX && node.maxX <= x2 && y1 <= node.minY && node.maxY <= y2) {
            return node.count;
        }

        // 情况 3：部分相交 => 判断当前点，再递归两个孩子
        int result = 0;
        const KdPoint& p = node.point;
        if (p.x >= x1 && p.x <= x2 && p.y >= y1 && p.y <= y2) ++result;
        result += rangeCount(node.left, x1, x2, y1, y2);
        result += rangeCount(node.right, x1, x2, y1, y2);
        return result;
    }

    void nearest(int idx, const KdPoint& query, KdPoint& best, double& bestDist) const {
        if (idx < 0) return;
        const Node& node = nodes_[idx];

        double dist = dist2(node.point, query);
        if (dist < bestDist) {
            bestDist = dist;
            best = node.point;
        }

        // 先走查询点所在的那一侧，让 bestDist 尽快变小，另一侧更容易被剪掉
        bool goLeft = node.axis == 0 ? (query.x < node.point.x) : (query.y < node.point.y);
        int nearChild = goLeft ? node.left : node.right;
        int farChild = goLeft ? node.right : node.left;

        nearest(nearChild, query, best, bestDist);

        // 远侧子树里「理论上最近」的可能距离 = 查询点到那个包围盒的距离；
        // 已经比当前最优还远，就整棵剪掉
        if (farChild >= 0 && boxDist2(nodes_[farChild], query) < bestDist) {
            nearest(farChild, query, best, bestDist);
        }
    }

    static double dist2(const KdPoint& a, const KdPoint& b) {
        double dx = a.x - b.x;
        double dy = a.y - b.y;
        return dx * dx + dy * dy;
    }

    // 点到包围盒的最短距离平方（点在盒内时为 0）
    static double boxDist2(const Node& node, const KdPoint& q) {
        double dx = max(0.0, max(node.minX - q.x, q.x - node.maxX));
        double dy = max(0.0, max(node.minY - q.y, q.y - node.maxY));
        return dx * dx + dy * dy;
    }

    vector<KdPoint> pts_;
    vector<Node> nodes_;
    int root_ = -1;
};

int main() {
    // 用确定性的点集，避免每次运行结果不同
    vector<KdPoint> points;
    for (int i = 0; i < 10; ++i) {
        for (int j = 0; j < 10; ++j) points.push_back(KdPoint{static_cast<double>(i), static_cast<double>(j)});
    }
    KdTree tree(points);

    // ---- 矩形范围计数 ----
    struct Rect {
        double x1, x2, y1, y2;
    };
    const vector<Rect> rects = {{0, 4, 0, 4}, {3, 7, 2, 8}, {-5, 15, -5, 15}, {100, 200, 100, 200}};
    for (const Rect& r : rects) {
        int got = tree.rangeCount(r.x1, r.x2, r.y1, r.y2);
        int expect = 0;  // 暴力对照
        for (const KdPoint& p : points) {
            if (p.x >= r.x1 && p.x <= r.x2 && p.y >= r.y1 && p.y <= r.y2) ++expect;
        }
        cout << "[K-D Tree] 矩形 [" << r.x1 << "," << r.x2 << "]x[" << r.y1 << "," << r.y2
             << "] 命中 " << got << " 个点 (暴力=" << expect << ")" << endl;
        assert(got == expect);
    }

    // ---- 最近邻 ----
    const vector<KdPoint> queries = {{0.2, 0.3}, {5.5, 5.4}, {9.9, 9.9}, {-3.0, 4.0}};
    for (const KdPoint& q : queries) {
        KdPoint got = tree.nearest(q.x, q.y);
        KdPoint expect;  // 暴力对照：线性扫描求最近
        double bestDist = 1e300;
        for (const KdPoint& p : points) {
            double d = (p.x - q.x) * (p.x - q.x) + (p.y - q.y) * (p.y - q.y);
            if (d < bestDist) {
                bestDist = d;
                expect = p;
            }
        }
        cout << "[K-D Tree] 查询点 (" << q.x << "," << q.y << ") 最近点 (" << got.x << "," << got.y
             << ")" << endl;
        double gotDist = (got.x - q.x) * (got.x - q.x) + (got.y - q.y) * (got.y - q.y);
        assert(fabs(gotDist - bestDist) < 1e-9);
    }

    cout << "algo_kd_tree: all checks passed" << endl;
    return 0;
}
