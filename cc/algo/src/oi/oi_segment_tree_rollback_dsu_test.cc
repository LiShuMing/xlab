// 独立的 main 测试入口；无第三方框架，-DNDEBUG 不会禁用检查。
#include "../include/fwd.h"
#include "offline_dynamic_connectivity.h"

#include <iterator>
#include <random>

namespace {

using oi::Kind;
using oi::Operation;

class Tests {
public:
    void require(bool ok, const std::string& message) {
        ++checks_;
        if (!ok) throw std::runtime_error(message);
    }

    template <typename Exception, typename Action>
    void throws(Action action, const std::string& message) {
        bool caught = false;
        try {
            action();
        } catch (const Exception&) {
            caught = true;
        }
        require(caught, message);
    }

    template <typename Action>
    void run(const char* name, Action action) {
        action();
        ++groups_;
        std::cout << "PASS " << name << '\n';
    }

    int checks() const { return checks_; }
    int groups() const { return groups_; }

private:
    int checks_ = 0;
    int groups_ = 0;
};

// 独立参照：不使用时间树、生存区间或并查集。
// 按原始时间顺序维护边集合；每次查询重建邻接表，用 BFS 从起点找终点。
// 它很慢，但小图下容易验证，能避免“两个相似实现共享同一个错误”。
std::vector<oi::Answer> brute(int vertices, const std::vector<Operation>& operations) {
    std::set<oi::Edge> active;
    std::vector<oi::Answer> answers;
    for (std::size_t t = 0; t < operations.size(); ++t) {
        const auto& op = operations[t];
        const oi::Edge edge = {std::min(op.u, op.v), std::max(op.u, op.v)};
        if (op.kind == Kind::Add) {
            if (!active.insert(edge).second) throw std::runtime_error("invalid oracle add");
        } else if (op.kind == Kind::Remove) {
            if (active.erase(edge) != 1) throw std::runtime_error("invalid oracle remove");
        } else {
            std::vector<std::vector<int>> adjacent(static_cast<std::size_t>(vertices));
            for (const auto& e : active) {
                adjacent[e.first].push_back(e.second);
                adjacent[e.second].push_back(e.first);
            }
            std::vector<bool> seen(static_cast<std::size_t>(vertices), false);
            std::queue<int> ready;
            ready.push(op.u);
            seen[op.u] = true;
            while (!ready.empty()) {
                const int u = ready.front();
                ready.pop();
                for (int v : adjacent[u]) {
                    if (!seen[v]) {
                        seen[v] = true;
                        ready.push(v);
                    }
                }
            }
            answers.push_back({static_cast<int>(t), op.u, op.v, seen[op.v]});
        }
    }
    return answers;
}

void equalAnswers(Tests& tests, const std::vector<oi::Answer>& actual,
                  const std::vector<oi::Answer>& expected, const std::string& label) {
    tests.require(actual.size() == expected.size(), label + ": answer count");
    for (std::size_t i = 0; i < expected.size(); ++i) {
        const auto& a = actual[i];
        const auto& e = expected[i];
        tests.require(a.time == e.time && a.u == e.u && a.v == e.v && a.connected == e.connected,
                      label + ": mismatch at answer " + std::to_string(i));
    }
}

void testRollback(Tests& tests) {
    oi::RollbackDsu dsu(6);
    const std::string initial = dsu.state();
    const auto empty = dsu.snapshot();
    tests.require(dsu.unite(0, 1) && dsu.unite(2, 3), "two disjoint merges");
    const auto outer = dsu.snapshot();
    const std::string outer_state = dsu.state();
    tests.require(dsu.unite(1, 2), "balanced merge");
    const auto inner = dsu.snapshot();
    const std::string inner_state = dsu.state();
    tests.require(dsu.connected(1, 3) && dsu.find(3) == dsu.find(0), "find through two levels");
    tests.require(dsu.state() == inner_state, "find/query must not compress paths");
    tests.require(!dsu.unite(0, 3) && !dsu.unite(5, 5), "cycle/self-loop are no-ops");
    tests.require(dsu.snapshot() == inner, "no-op must not push history");
    tests.require(dsu.unite(4, 5) && dsu.unite(3, 4), "nested merges");
    tests.require(dsu.components() == 1 && dsu.componentSize(5) == 6, "merged metadata");
    dsu.rollback(inner);
    tests.require(dsu.state() == inner_state, "restore all fields, not only connectivity");
    dsu.rollback(outer);
    tests.require(dsu.state() == outer_state, "restore outer snapshot");
    tests.require(!dsu.connected(1, 3) && dsu.componentSize(3) == 2, "branches separated");
    // 在同一父状态上改走另一分支，再回滚；检查上一个分支的 size 没有泄漏。
    dsu.unite(1, 4);
    dsu.rollback(outer);
    tests.require(dsu.state() == outer_state, "sibling branch isolation");
    dsu.rollback(empty);
    dsu.rollback(empty);
    tests.require(dsu.state() == initial && dsu.components() == 6, "root fully restored");
    tests.throws<std::invalid_argument>([&] { dsu.rollback(1); }, "future snapshot rejected");
    tests.throws<std::out_of_range>([&] { dsu.find(-1); }, "negative vertex rejected");
    tests.throws<std::out_of_range>([&] { dsu.unite(0, 6); }, "large vertex rejected");
    tests.require(dsu.state() == initial, "invalid union is nonmutating");
    tests.throws<std::invalid_argument>([] { oi::RollbackDsu bad(0); }, "zero size rejected");
    tests.throws<std::invalid_argument>([] { oi::RollbackDsu bad(-1); }, "negative size rejected");
}

void testDemoAndTrace(Tests& tests) {
    const std::vector<Operation> operations = {
            {Kind::Add, 0, 1}, {Kind::Add, 1, 2}, {Kind::Query, 0, 2},
            {Kind::Remove, 0, 1}, {Kind::Query, 0, 2}, {Kind::Add, 0, 2},
            {Kind::Query, 0, 1}, {Kind::Remove, 0, 2}, {Kind::Query, 0, 1},
    };
    const oi::OfflineDynamicConnectivity solver(3, operations);
    const std::vector<oi::Answer> expected = {
            {2, 0, 2, true}, {4, 0, 2, false}, {6, 0, 1, true}, {8, 0, 1, false},
    };
    std::ostringstream trace;
    solver.explainSchedule(trace);
    equalAnswers(tests, solver.solve(&trace), expected, "hand-computed demo");
    equalAnswers(tests, solver.solve(), expected, "second solve starts fresh");
    equalAnswers(tests, solver.solve(), brute(3, operations), "demo versus BFS");
    tests.require(trace.str().find("alive=[0,3)") != std::string::npos, "deletion is exclusive");
    tests.require(trace.str().find("alive=[1,9)") != std::string::npos, "unremoved edge ends at T");
    tests.require(trace.str().find("STORE node=") != std::string::npos, "placement visible");
    tests.require(trace.str().find("QUERY t=4 0~2 => NO") != std::string::npos, "leaf visible");
    const std::string final = "ROLLBACK [0,9) undo=0 -> snapshot=0 | " + oi::RollbackDsu(3).state();
    tests.require(trace.str().find(final + '\n') != std::string::npos, "root trace restored");
}

void testBoundariesAndCycles(Tests& tests) {
    const std::vector<std::vector<Operation>> cases = {
            {},
            {{Kind::Query, 0, 0}},
            {{Kind::Query, 0, 2}},
            {{Kind::Add, 0, 1}},  // 没有任何询问，也必须安全完成 DFS/回滚。
            {{Kind::Add, 0, 1}, {Kind::Remove, 1, 0}, {Kind::Query, 0, 1}},
            {{Kind::Add, 1, 0}, {Kind::Query, 0, 1}, {Kind::Remove, 0, 1},
             {Kind::Query, 0, 1}, {Kind::Add, 0, 1}, {Kind::Query, 1, 0}},
            {{Kind::Add, 0, 0}, {Kind::Query, 0, 0}, {Kind::Query, 0, 1},
             {Kind::Remove, 0, 0}, {Kind::Query, 0, 0}},
            // 三角形的一条边可能是冗余合并，但删掉另一条后它又成为必要路径。
            {{Kind::Add, 0, 1}, {Kind::Add, 1, 2}, {Kind::Add, 0, 2},
             {Kind::Query, 0, 2}, {Kind::Remove, 1, 2}, {Kind::Query, 0, 2},
             {Kind::Remove, 0, 2}, {Kind::Query, 0, 2}},
    };
    for (std::size_t i = 0; i < cases.size(); ++i) {
        const oi::OfflineDynamicConnectivity solver(3, cases[i]);
        equalAnswers(tests, solver.solve(), brute(3, cases[i]), "boundary " + std::to_string(i));
    }
    const oi::OfflineDynamicConnectivity single(1, {{Kind::Query, 0, 0}});
    tests.require(single.solve()[0].connected, "a vertex is connected to itself without edges");
    const oi::OfflineDynamicConnectivity loop(1, {{Kind::Add, 0, 0}, {Kind::Query, 0, 0}});
    std::ostringstream trace;
    tests.require(loop.solve(&trace)[0].connected, "self-loop query");
    tests.require(trace.str().find("SKIP  0-0 stack=0") != std::string::npos,
                  "no-op merge leaves snapshot unchanged in trace");
}

void testInvalidInput(Tests& tests) {
    const std::vector<std::vector<Operation>> cases = {
            {{Kind::Remove, 0, 1}},
            {{Kind::Add, 0, 1}, {Kind::Add, 1, 0}},
            {{Kind::Add, 0, 1}, {Kind::Remove, 0, 1}, {Kind::Remove, 1, 0}},
            {{static_cast<Kind>(999), 0, 1}},
    };
    for (const auto& operations : cases) {
        tests.throws<std::invalid_argument>(
                [&] { oi::OfflineDynamicConnectivity bad(3, operations); },
                "invalid lifetime input");
    }
    for (Kind kind : {Kind::Add, Kind::Remove, Kind::Query}) {
        tests.throws<std::out_of_range>(
                [&] { oi::OfflineDynamicConnectivity bad(3, {{kind, -1, 0}}); },
                "negative endpoint");
        tests.throws<std::out_of_range>(
                [&] { oi::OfflineDynamicConnectivity bad(3, {{kind, 0, 3}}); },
                "large endpoint");
    }
    tests.throws<std::invalid_argument>(
            [] { oi::OfflineDynamicConnectivity bad(0, {}); }, "zero vertices rejected");
}

void testRandomAgainstBfs(Tests& tests) {
    std::mt19937 random(20261107);
    int queries = 0;
    for (int trial = 0; trial < 500; ++trial) {
        const int vertices = 1 + static_cast<int>(random() % 8);
        const int steps = 1 + static_cast<int>(random() % 100);
        std::set<oi::Edge> active;
        std::vector<Operation> operations;
        for (int t = 0; t < steps; ++t) {
            int u = static_cast<int>(random() % static_cast<unsigned>(vertices));
            int v = static_cast<int>(random() % static_cast<unsigned>(vertices));
            const oi::Edge edge = {std::min(u, v), std::max(u, v)};
            const auto choice = random() % 3;
            if (choice == 0 && active.count(edge) == 0) {
                active.insert(edge);
                operations.push_back({Kind::Add, u, v});
            } else if (choice == 1 && !active.empty()) {
                // 随机删除一条确实存在的边；故意反转端点，覆盖无向边规范化。
                auto found = active.begin();
                std::advance(found, static_cast<std::ptrdiff_t>(random() % active.size()));
                operations.push_back({Kind::Remove, found->second, found->first});
                active.erase(found);
            } else {
                operations.push_back({Kind::Query, u, v});
            }
        }
        operations.push_back({Kind::Query, 0, vertices - 1});
        const auto expected = brute(vertices, operations);
        queries += static_cast<int>(expected.size());
        const oi::OfflineDynamicConnectivity solver(vertices, operations);
        equalAnswers(tests, solver.solve(), expected, "seed=20261107 trial=" + std::to_string(trial));
    }
    std::cout << "  random streams=500, BFS queries compared=" << queries << '\n';
}

}  // namespace

int main() {
    try {
        Tests tests;
        tests.run("DSU nested snapshots / size / no-op / branch isolation", [&] { testRollback(tests); });
        tests.run("hand-computed demo / trace / repeated solve", [&] { testDemoAndTrace(tests); });
        tests.run("empty timeline / lifetime boundaries / re-add / cycles / self-loop",
                  [&] { testBoundariesAndCycles(tests); });
        tests.run("invalid vertices / duplicate add / missing remove", [&] { testInvalidInput(tests); });
        tests.run("500 deterministic streams versus independent BFS", [&] { testRandomAgainstBfs(tests); });
        std::cout << "All " << tests.groups() << " groups passed; " << tests.checks()
                  << " checks (also active under -DNDEBUG).\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
