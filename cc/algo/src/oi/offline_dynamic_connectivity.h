#pragma once

// 时间线段树 + 可回滚并查集（cc/algo/src/oi）。
// 教学目标：支持加边、删边和连通性询问，但绝不让并查集直接执行“删边”。
// 1. 离线配对 add/remove，得到每条边的生存区间 [begin, end)。
// 2. 将区间拆成时间线段树的 O(log T) 个节点，各存一份边。
// 3. DFS 进入节点时加边，离开节点时回滚；叶子 t 的状态就是时刻 t 的图。
// 算法思路参考（实现与教学用例为本目录独立编写）：
// https://oi-wiki.org/topic/segment-tree-offline/
// https://cp-algorithms.com/data_structures/deleting_in_log_n.html

#include <algorithm>
#include <cstddef>
#include <limits>
#include <map>
#include <numeric>
#include <ostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace oi {

class RollbackDsu {
public:
    using Snapshot = std::size_t;

    explicit RollbackDsu(int vertices) {
        if (vertices <= 0) throw std::invalid_argument("vertices must be positive");
        parent_.resize(static_cast<std::size_t>(vertices));
        size_.assign(parent_.size(), 1);
        std::iota(parent_.begin(), parent_.end(), 0);
        components_ = vertices;
    }

    int find(int vertex) const {
        if (vertex < 0 || static_cast<std::size_t>(vertex) >= parent_.size()) {
            throw std::out_of_range("vertex out of range");
        }
        // 不做路径压缩！find 必须只读，否则查询也会改写大量 parent，增加回滚负担。
        // 按大小合并已保证树高 O(log N)，所以这里的最坏复杂度是 O(log N)。
        while (parent_[vertex] != vertex) vertex = parent_[vertex];
        return vertex;
    }

    bool connected(int u, int v) const { return find(u) == find(v); }
    int componentSize(int vertex) const { return size_[find(vertex)]; }
    int components() const { return components_; }
    Snapshot snapshot() const { return history_.size(); }

    bool unite(int u, int v) {
        int large = find(u);
        int small = find(v);
        // 自环、重合路径、环中的冗余边都可能走这里：没有修改，就不入栈。
        // 因此不能“加了几条边就撤销几次”，必须回滚到进入节点前的栈长度。
        if (large == small) return false;
        if (size_[large] < size_[small]) std::swap(large, small);
        history_.push_back({small, large, size_[large]});
        parent_[small] = large;
        size_[large] += size_[small];
        --components_;
        return true;
    }

    // 只允许回到当前历史栈的前缀；snapshot 不是可以永久跨分支复用的版本 ID。
    void rollback(Snapshot target) {
        if (target > history_.size()) throw std::invalid_argument("snapshot is in the future");
        while (history_.size() > target) {
            const Change change = history_.back();
            history_.pop_back();
            // 后发生的合并先撤销，故此时 large 已回到这次合并完成时的状态。
            // small 在合并前一定是根，其旧 parent 就是它自己；它的 size 从未改过。
            parent_[change.small] = change.small;
            size_[change.large] = change.old_large_size;
            ++components_;
        }
    }

    // 仅用于教学和测试。size 只有在对应点是根时才代表连通块大小。
    // 打印原始 parent/size（而不只打印连通性），可以发现不完整的回滚。
    std::string state() const {
        std::ostringstream out;
        out << "parent=[";
        for (std::size_t i = 0; i < parent_.size(); ++i) {
            if (i != 0) out << ',';
            out << parent_[i];
        }
        out << "] size=[";
        for (std::size_t i = 0; i < size_.size(); ++i) {
            if (i != 0) out << ',';
            out << size_[i];
        }
        out << "] components=" << components_;
        return out.str();
    }

private:
    struct Change {
        int small;
        int large;
        int old_large_size;
    };
    std::vector<int> parent_;
    std::vector<int> size_;
    std::vector<Change> history_;
    int components_ = 0;
};

enum class Kind { Add, Remove, Query };

struct Operation {
    Kind kind;
    int u;
    int v;
};

using Edge = std::pair<int, int>;

struct Lifetime {
    Edge edge;
    int begin;
    int end;
};

struct Answer {
    int time;
    int u;
    int v;
    bool connected;
};

class OfflineDynamicConnectivity {
public:
    // 语义：初始图为空；operations[t] 执行后的状态对应叶子 [t, t+1)。
    // 无向简单边：端点交换视为同一条边；允许自环，不允许同一边重复处于活跃状态。
    OfflineDynamicConnectivity(int vertices, std::vector<Operation> operations)
            : vertices_(vertices), operations_(std::move(operations)) {
        if (vertices <= 0) throw std::invalid_argument("vertices must be positive");
        // 节点下标、时间使用 int；先检查再进行窄化和 4*T 分配。
        if (operations_.size() > static_cast<std::size_t>(std::numeric_limits<int>::max() / 4)) {
            throw std::length_error("too many operations");
        }
        times_ = static_cast<int>(operations_.size());
        collectLifetimes();
        buckets_.resize(static_cast<std::size_t>(times_) * 4 + 1);
        for (const Lifetime& life : lifetimes_) {
            insert(1, 0, times_, life.begin, life.end, life.edge);
        }
    }

    const std::vector<Lifetime>& lifetimes() const { return lifetimes_; }

    // solve 的状态全部为局部变量，重复运行不会继承上一次的并查集或答案。
    std::vector<Answer> solve(std::ostream* trace = nullptr) const {
        RollbackDsu dsu(vertices_);
        std::vector<Answer> answers;
        if (times_ != 0) dfs(1, 0, times_, dsu, answers, trace, 0);
        return answers;
    }

    void explainSchedule(std::ostream& out) const {
        out << "=== 1. 生存区间（左闭右开）与时间树上的存放位置 ===\n";
        for (const Lifetime& life : lifetimes_) {
            out << "EDGE " << life.edge.first << '-' << life.edge.second << " alive=["
                << life.begin << ',' << life.end << ")\n";
            // 与 insert 使用相同的区间拆分规则，但只输出位置，不修改 buckets。
            explainPlacement(1, 0, times_, life.begin, life.end, out, 1);
        }
    }

private:
    static Edge normalized(int u, int v) { return {std::min(u, v), std::max(u, v)}; }

    void collectLifetimes() {
        std::map<Edge, int> active;
        for (int t = 0; t < times_; ++t) {
            const Operation& op = operations_[t];
            if (op.u < 0 || op.u >= vertices_ || op.v < 0 || op.v >= vertices_) {
                throw std::out_of_range("vertex out of range at time " + std::to_string(t));
            }
            const Edge edge = normalized(op.u, op.v);
            switch (op.kind) {
            case Kind::Add:
                if (!active.emplace(edge, t).second) {
                    throw std::invalid_argument("duplicate add at time " + std::to_string(t));
                }
                break;
            case Kind::Remove: {
                const auto found = active.find(edge);
                if (found == active.end()) {
                    throw std::invalid_argument("remove inactive edge at time " + std::to_string(t));
                }
                // 删除时刻不属于生存区间。将来可以重新加入，形成另一个不相交区间。
                lifetimes_.push_back({edge, found->second, t});
                active.erase(found);
                break;
            }
            case Kind::Query:
                break;
            default:
                throw std::invalid_argument("unknown operation kind");
            }
        }
        for (const auto& entry : active) {
            // 到输入结束仍未删除的边，生存期一直延续到时间轴右端点 T。
            lifetimes_.push_back({entry.first, entry.second, times_});
        }
    }

    void insert(int node, int left, int right, int begin, int end, Edge edge) {
        if (begin >= right || end <= left) return;
        if (begin <= left && right <= end) {
            buckets_[node].push_back(edge);
            // 完整覆盖后停在这里，不能再把同一条边复制到所有后代。
            return;
        }
        const int mid = left + (right - left) / 2;
        insert(node * 2, left, mid, begin, end, edge);
        insert(node * 2 + 1, mid, right, begin, end, edge);
    }

    static void explainPlacement(int node, int left, int right, int begin, int end,
                                 std::ostream& out, int depth) {
        if (begin >= right || end <= left) return;
        if (begin <= left && right <= end) {
            out << std::string(static_cast<std::size_t>(depth) * 2, ' ')
                << "STORE node=" << node << " interval=[" << left << ',' << right << ")\n";
            return;
        }
        const int mid = left + (right - left) / 2;
        explainPlacement(node * 2, left, mid, begin, end, out, depth + 1);
        explainPlacement(node * 2 + 1, mid, right, begin, end, out, depth + 1);
    }

    void dfs(int node, int left, int right, RollbackDsu& dsu, std::vector<Answer>& answers,
             std::ostream* trace, int depth) const {
        const auto checkpoint = dsu.snapshot();
        const std::string indent = trace ? std::string(static_cast<std::size_t>(depth) * 2, ' ') : "";
        if (trace) {
            *trace << indent << "ENTER [" << left << ',' << right << ") snapshot="
                   << checkpoint << " | " << dsu.state() << '\n';
        }
        for (const Edge& edge : buckets_[node]) {
            const bool merged = dsu.unite(edge.first, edge.second);
            if (trace) {
                *trace << indent << "  " << (merged ? "APPLY " : "SKIP  ") << edge.first
                       << '-' << edge.second << " stack=" << dsu.snapshot() << " | "
                       << dsu.state() << '\n';
            }
        }

        // 核心不变量：应用本节点后，DSU 包含根到当前节点路径上的全部边的效果。
        // 对任意有效区间，覆盖叶子 t 的规范分解节点恰好在该路径上出现一次。
        // 因此到了叶子，DSU 对应的就是该时刻所有活跃边形成的连通关系。
        if (right - left == 1) {
            const Operation& op = operations_[left];
            if (op.kind == Kind::Query) {
                const bool connected = dsu.connected(op.u, op.v);
                answers.push_back({left, op.u, op.v, connected});
                if (trace) {
                    *trace << indent << "  QUERY t=" << left << ' ' << op.u << '~' << op.v
                           << " => " << (connected ? "YES" : "NO") << '\n';
                }
            }
        } else {
            const int mid = left + (right - left) / 2;
            dfs(node * 2, left, mid, dsu, answers, trace, depth + 1);
            // 左子树已经恢复到父节点状态；不会把只在左侧活跃的边带进右子树。
            dfs(node * 2 + 1, mid, right, dsu, answers, trace, depth + 1);
        }
        const auto changes = dsu.snapshot() - checkpoint;
        dsu.rollback(checkpoint);
        if (trace) {
            *trace << indent << "ROLLBACK [" << left << ',' << right << ") undo=" << changes
                   << " -> snapshot=" << checkpoint << " | " << dsu.state() << '\n';
        }
    }

    int vertices_;
    int times_ = 0;
    std::vector<Operation> operations_;
    std::vector<Lifetime> lifetimes_;
    std::vector<std::vector<Edge>> buckets_;
};

}  // namespace oi
