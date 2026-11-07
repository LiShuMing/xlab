/**
 * 树上差分求「路径加、单点查询」
 * 例题：洛谷 P3128 [USACO15DEC] Max Flow P
 *       https://www.luogu.com.cn/problem/P3128
 *
 * 题意：n 个点的树和 K 条路径，每条路径给路径上每个点压力 +1，问最大压力。
 *
 * 点差分公式（本文件实现）：
 *   diff[from] += 1, diff[to] += 1, diff[lca] -= 1, diff[parent(lca)] -= 1
 *   收尾做一遍子树求和，pressures[v] 就是 v 的压力。
 * 边差分对照（边权挂在子结点上）：
 *   diff[from] += 1, diff[to] += 1, diff[lca] -= 2，不需要动 parent(lca)。
 *
 * 为什么是四个点：diff[p] += v 在子树和语义下等价于「p 到根整条链 +v」。
 *   +1: 根→from、根→to 各一次；-1: 根→lca（去掉重复的公共前缀）；
 *   -1: 根→parent(lca)（把上一步误减掉的祖先补回去，只留 lca 那一份）。
 *
 * 复杂度：倍增预处理 O(n log n)，每条路径 O(log n)，收尾 O(n)；
 * 总计 O((n + K) log n)，空间 O(n log n)。
 *
 * 坑：
 *   - lca 是根时 parent(lca) 不存在：用 0 号虚拟点承接，0 号点不参与答案；
 *   - 子树和必须子先父后。n = 5e4 的链上递归 DFS 会爆栈，这里全程迭代；
 *   - 点差分写成 -2 就成了边差分，压力会整体少算。
 */

#include "../include/fwd.h"

#include <cstdlib>
#include <random>

namespace {

using EdgeList = std::vector<std::pair<int, int>>;

// 统计树上路径覆盖次数。graph 用 1-based 编号，graph[0] 不使用。
class TreePathCounter {
public:
    TreePathCounter(const std::vector<std::vector<int>>& graph, int root)
        : vertex_count_(static_cast<int>(graph.size()) - 1),
          depth_(vertex_count_ + 1, 0),
          parent_(vertex_count_ + 1, 0),
          diff_(vertex_count_ + 1, 0) {
        BuildTree(graph, root);
        BuildAncestorTable();
    }

    // 最近公共祖先：先把深的抬到同层，再从高位往低位一起跳
    int Lca(int from, int to) const {
        if (depth_[from] < depth_[to]) std::swap(from, to);
        const int rise = depth_[from] - depth_[to];
        for (int level = 0; level < log_count_; ++level) {
            if (((rise >> level) & 1) != 0) from = ancestors_[level][from];
        }
        if (from == to) return from;
        for (int level = log_count_ - 1; level >= 0; --level) {
            if (ancestors_[level][from] != ancestors_[level][to]) {
                from = ancestors_[level][from];
                to = ancestors_[level][to];
            }
        }
        return ancestors_[0][from];
    }

    // 路径 (from, to) 上每个点压力 +1
    void AddPath(int from, int to) {
        const int ancestor = Lca(from, to);
        ++diff_[from];
        ++diff_[to];
        --diff_[ancestor];
        --diff_[parent_[ancestor]];  // ancestor 为根时落到 0 号虚拟点
    }

    // 后序累加：pressures[v] = diff[v] + 所有子结点的 pressures
    std::vector<long long> Pressures() const {
        std::vector<long long> pressures = diff_;
        for (int i = static_cast<int>(order_.size()) - 1; i > 0; --i) {
            const int vertex = order_[i];
            pressures[parent_[vertex]] += pressures[vertex];
        }
        return pressures;
    }

    long long MaxPressure() const {
        const std::vector<long long> pressures = Pressures();
        long long best = 0;
        for (int vertex = 1; vertex <= vertex_count_; ++vertex) {
            best = std::max(best, pressures[vertex]);
        }
        return best;
    }

private:
    // BFS 同时得到父指针、深度和遍历序。链状树深度可达 n，递归 DFS 会爆栈。
    void BuildTree(const std::vector<std::vector<int>>& graph, int root) {
        std::vector<char> visited(vertex_count_ + 1, 0);
        std::queue<int> pending;
        visited[root] = 1;
        pending.push(root);
        order_.push_back(root);
        while (!pending.empty()) {
            const int vertex = pending.front();
            pending.pop();
            for (int neighbor : graph[vertex]) {
                if (visited[neighbor] != 0) continue;
                visited[neighbor] = 1;
                parent_[neighbor] = vertex;
                depth_[neighbor] = depth_[vertex] + 1;
                order_.push_back(neighbor);
                pending.push(neighbor);
            }
        }
    }

    // ancestors_[level][v] = v 的 2^level 级祖先；保证 2^log_count_ > vertex_count_
    void BuildAncestorTable() {
        log_count_ = 1;
        while ((1 << log_count_) <= vertex_count_) ++log_count_;
        ancestors_.assign(log_count_, std::vector<int>(vertex_count_ + 1, 0));
        ancestors_[0] = parent_;
        for (int level = 1; level < log_count_; ++level) {
            for (int vertex = 1; vertex <= vertex_count_; ++vertex) {
                ancestors_[level][vertex] = ancestors_[level - 1][ancestors_[level - 1][vertex]];
            }
        }
    }

    int vertex_count_ = 0;
    int log_count_ = 0;
    std::vector<int> depth_;
    std::vector<int> parent_;
    std::vector<long long> diff_;
    std::vector<int> order_;  // BFS 序：父亲一定排在儿子前面
    std::vector<std::vector<int>> ancestors_;
};

// 基线：不用差分也不用倍增。沿父指针逐点加，LCA 用最朴素的抬升法。
std::vector<long long> BrutePressures(const std::vector<std::vector<int>>& graph,
                                      const EdgeList& paths, int root) {
    const int vertex_count = static_cast<int>(graph.size()) - 1;
    std::vector<int> parent(vertex_count + 1, 0);
    std::vector<int> depth(vertex_count + 1, 0);
    std::vector<char> visited(vertex_count + 1, 0);
    std::queue<int> pending;
    visited[root] = 1;
    pending.push(root);
    while (!pending.empty()) {
        const int vertex = pending.front();
        pending.pop();
        for (int neighbor : graph[vertex]) {
            if (visited[neighbor] != 0) continue;
            visited[neighbor] = 1;
            parent[neighbor] = vertex;
            depth[neighbor] = depth[vertex] + 1;
            pending.push(neighbor);
        }
    }
    std::vector<long long> pressures(vertex_count + 1, 0);
    for (const auto& path : paths) {
        int from = path.first;
        int to = path.second;
        while (depth[from] > depth[to]) {
            ++pressures[from];
            from = parent[from];
        }
        while (depth[to] > depth[from]) {
            ++pressures[to];
            to = parent[to];
        }
        while (from != to) {
            ++pressures[from];
            ++pressures[to];
            from = parent[from];
            to = parent[to];
        }
        ++pressures[from];  // from == to == lca，只加一次
    }
    return pressures;
}

// 链 1-2-...-n
std::vector<std::vector<int>> MakeChain(int vertex_count) {
    std::vector<std::vector<int>> graph(vertex_count + 1);
    for (int vertex = 2; vertex <= vertex_count; ++vertex) {
        graph[vertex].push_back(vertex - 1);
        graph[vertex - 1].push_back(vertex);
    }
    return graph;
}

// 星形：1 连其余所有点
std::vector<std::vector<int>> MakeStar(int vertex_count) {
    std::vector<std::vector<int>> graph(vertex_count + 1);
    for (int vertex = 2; vertex <= vertex_count; ++vertex) {
        graph[1].push_back(vertex);
        graph[vertex].push_back(1);
    }
    return graph;
}

// 与基线逐点比对后返回差分结果。期望值由基线现场算出，不硬编码记忆中的答案。
std::vector<long long> CheckCase(const std::vector<std::vector<int>>& graph,
                                 const EdgeList& paths, int root) {
    TreePathCounter counter(graph, root);
    for (const auto& path : paths) counter.AddPath(path.first, path.second);
    const std::vector<long long> got = counter.Pressures();
    const std::vector<long long> want = BrutePressures(graph, paths, root);
    for (int vertex = 1; vertex < static_cast<int>(got.size()); ++vertex) {
        if (got[vertex] != want[vertex]) {
            std::cout << "FAIL: vertex " << vertex << " got=" << got[vertex]
                      << " want=" << want[vertex] << std::endl;
            std::abort();
        }
    }
    const long long want_max = *std::max_element(want.begin() + 1, want.end());
    if (counter.MaxPressure() != want_max) {
        std::cout << "FAIL: max pressure differs, want=" << want_max << std::endl;
        std::abort();
    }
    return got;
}

}  // namespace

int main() {
    // 1) 链 1-2-3：路径 (1,3) 覆盖三点，(2,2) 只加中间那个
    {
        const std::vector<std::vector<int>> graph = MakeChain(3);
        const std::vector<long long> pressures = CheckCase(graph, {{1, 3}, {2, 2}}, 1);
        std::cout << "[树差分] 链 1-2-3，路径 (1,3)+(2,2)：压力 = " << pressures[1] << ' '
                  << pressures[2] << ' ' << pressures[3] << std::endl;
        if (pressures[1] != 1 || pressures[2] != 2 || pressures[3] != 1) std::abort();
    }

    // 2) 星形：两次跨叶路径，根被两条路径各压一次
    {
        const std::vector<std::vector<int>> graph = MakeStar(5);
        const std::vector<long long> pressures = CheckCase(graph, {{2, 3}, {4, 5}}, 1);
        std::cout << "[树差分] 星形两次跨叶路径：根 = " << pressures[1]
                  << "，叶子 = " << pressures[2] << std::endl;
        if (pressures[1] != 2 || pressures[2] != 1 || pressures[5] != 1) std::abort();
    }

    // 3) 单点树：lca 就是根，parent(lca) 不存在，靠 0 号虚拟点承接
    {
        const std::vector<long long> pressures = CheckCase(std::vector<std::vector<int>>(2),
                                                          {{1, 1}, {1, 1}, {1, 1}}, 1);
        std::cout << "[树差分] 单点树 3 次自环路径：压力 = " << pressures[1] << std::endl;
        if (pressures[1] != 3) std::abort();
    }

    // 4) 随机对拍：随机树 + 随机端点（含 from == to 的自环）
    std::mt19937 random_engine(20261107);
    constexpr int kRandomTrees = 2000;
    for (int round = 0; round < kRandomTrees; ++round) {
        const int vertex_count = 1 + static_cast<int>(random_engine() % 40);
        std::vector<std::vector<int>> graph(vertex_count + 1);
        for (int vertex = 2; vertex <= vertex_count; ++vertex) {
            const int parent = 1 + static_cast<int>(random_engine() % (vertex - 1));
            graph[parent].push_back(vertex);
            graph[vertex].push_back(parent);
        }
        EdgeList paths;
        const int path_count = static_cast<int>(random_engine() % 30);
        for (int i = 0; i < path_count; ++i) {
            const int from = 1 + static_cast<int>(random_engine() % vertex_count);
            const int to = 1 + static_cast<int>(random_engine() % vertex_count);
            paths.emplace_back(from, to);
        }
        CheckCase(graph, paths, 1);
    }
    std::cout << "[树差分] " << kRandomTrees << " 组随机树 + 随机路径：与逐点基线一致"
              << std::endl;

    // 5) 规模冒烟：5e4 点的链（深度 5e4，最考验爆栈）+ 1e5 条 (1, n) 路径。
    //    每条路径覆盖所有点，所以每点压力必然等于 K，可解析验证。
    {
        constexpr int kVertexCount = 50000;
        constexpr int kPathCount = 100000;
        const std::vector<std::vector<int>> graph = MakeChain(kVertexCount);
        TreePathCounter counter(graph, 1);
        for (int i = 0; i < kPathCount; ++i) counter.AddPath(1, kVertexCount);
        const std::vector<long long> pressures = counter.Pressures();
        const auto range = std::minmax_element(pressures.begin() + 1, pressures.end());
        std::cout << "[树差分] 链 n=" << kVertexCount << ", K=" << kPathCount << "：压力区间 ["
                  << *range.first << ", " << *range.second << "]，最大 = " << counter.MaxPressure()
                  << std::endl;
        if (*range.first != kPathCount || *range.second != kPathCount) std::abort();
    }

    std::cout << "oi_tree_difference: all checks passed" << std::endl;
    return 0;
}
