#include "../include/fwd.h"

// LeetCode 1857. Largest Color Value in a Directed Graph
//
// 【问题】
// 有向图，n 个节点编号 0..n-1，每个节点一种颜色（colors[i] 为小写字母）。
// 一条路径的"颜色值"= 该路径上出现次数最多的那种颜色的个数。
// 求所有路径中颜色值的最大值；若图中存在环，返回 -1。
//
// 【核心直觉】
// 把"某种颜色在这条路径上出现了几次"做成 DP 状态，沿拓扑序推进。
//
//   best[v][c] = 所有以 v 结尾的路径中，颜色 c 出现次数的最大值
//
// u -> v 的转移分两步，顺序不能反：
//
//     best[u] = [a:1, b:0, c:2, ...]     26 格向量
//                 │
//                 │  ① 整份继承，逐格取 max
//                 ↓
//     best[v] = [a:1, b:0, c:2, ...]
//                 │
//                 │  ② 再给 v 自己的颜色 +1
//                 ↓
//     best[v] = [a:1, b:1, c:2, ...]     (假设 colors[v] == 'b')
//
// 先继承再自增：下游要拿到"包含 u 自己颜色"的完整值。
//
// 【为什么 26 个颜色可以各自独立取 max】
// 答案只问"某个颜色的最大计数"：
//     max(路径 P, 颜色 c) P 上 c 的个数
//   = max(颜色 c, 路径 P) P 上 c 的个数
// 两个 max 可交换，所以每个颜色单独做一遍最长路即可，
// 不要求 26 个分量来自同一条真实路径。
//
// 【复杂度】
// O((n + m) * 26) 时间，O(n * 26) 空间，n 为点数、m 为边数。
//
// 【易错点】
// 1. 判环不能用"队列空了"——循环退出条件本身就是它，恒真。
//    正确判据是"进入过拓扑序的节点数 == n"（与 LeetCode 207 同一陷阱）。
// 2. 转移里先继承、后自增，顺序颠倒会让下游少算一个自身颜色。
// 3. 节点编号连续 0..n-1，用 vector 而非 unordered_map：省哈希、可索引。

class Solution {
public:
    int largestPathValue(string colors, vector<vector<int>>& edges) {
        const int n = static_cast<int>(colors.size());
        constexpr int kAlpha = 26;

        // 邻接表 + 入度：节点编号连续，直接用数组
        vector<vector<int>> graph(n);
        vector<int> in_degree(n, 0);
        for (const auto& edge : edges) {
            graph[edge[0]].push_back(edge[1]);
            ++in_degree[edge[1]];
        }

        // best[v][c]：以 v 结尾的路径上，颜色 c 最多出现几次
        vector<vector<int>> best(n, vector<int>(kAlpha, 0));

        // 没有超级源：路径可以从任意点起步，所有入度为 0 的点同时入队
        vector<int> ready;
        ready.reserve(n);
        for (int v = 0; v < n; ++v) {
            if (in_degree[v] == 0) {
                ready.push_back(v);
            }
        }

        int settled = 0;  // 已确定 best 的节点数，用于判环
        int ans = 0;

        while (!ready.empty()) {
            int u = ready.back();
            ready.pop_back();
            ++settled;

            // u 的前驱此时都已传播完毕，best[u] 已是终值：先记上 u 自己的颜色
            const int self_color = colors[u] - 'a';
            ++best[u][self_color];

            // 再把整份 26 色向量推给下游（含刚自增的那一格）
            for (int v : graph[u]) {
                for (int c = 0; c < kAlpha; ++c) {
                    if (best[u][c] > best[v][c]) {
                        best[v][c] = best[u][c];
                    }
                }
                if (--in_degree[v] == 0) {
                    ready.push_back(v);
                }
            }

            // 出队即终值，顺带刷新全局答案
            for (int c = 0; c < kAlpha; ++c) {
                if (best[u][c] > ans) {
                    ans = best[u][c];
                }
            }
        }

        // 有环时环上的点与"只能从环到达"的点都进不了拓扑序
        return settled == n ? ans : -1;
    }
};

namespace {

int g_failed = 0;
int g_cases = 0;

void expect_eq(const string& name, int got, int want) {
    ++g_cases;
    if (got != want) {
        ++g_failed;
        cout << "[FAIL] " << name << "  got=" << got << " want=" << want << "\n";
    }
}

// 固定种子的线性同余，保证用例可重现，且不额外引入 <random>
unsigned g_seed = 20261101u;
unsigned next_rand() {
    g_seed = g_seed * 1103515245u + 12345u;
    return (g_seed >> 16) & 0x7fffu;
}

// 暴力参考解：三色 DFS 判环；无环则枚举所有路径逐条统计
int brute(const string& colors, const vector<vector<int>>& edges) {
    const int n = static_cast<int>(colors.size());
    vector<vector<int>> graph(n);
    for (const auto& edge : edges) {
        graph[edge[0]].push_back(edge[1]);
    }

    // 0 = 未访问，1 = 在当前栈上，2 = 已完成
    vector<int> state(n, 0);
    bool has_cycle = false;
    function<void(int)> detect = [&](int u) {
        state[u] = 1;
        for (int v : graph[u]) {
            if (state[v] == 1) {
                has_cycle = true;
                return;
            }
            if (state[v] == 0) {
                detect(v);
                if (has_cycle) {
                    return;
                }
            }
        }
        state[u] = 2;
    };
    for (int i = 0; i < n && !has_cycle; ++i) {
        if (state[i] == 0) {
            detect(i);
        }
    }
    if (has_cycle) {
        return -1;
    }

    // DAG 上从每个点出发枚举全部路径
    int ans = 0;
    vector<int> cnt(26, 0);
    function<void(int)> walk = [&](int u) {
        const int c = colors[u] - 'a';
        ++cnt[c];
        if (cnt[c] > ans) {
            ans = cnt[c];
        }
        for (int v : graph[u]) {
            walk(v);
        }
        --cnt[c];
    };
    for (int s = 0; s < n; ++s) {
        walk(s);
    }
    return ans;
}

}  // namespace

int main() {
    Solution sol;

    // ---- 手算用例 ----
    {
        // 路径 0(a)->2(a)->3(c)->4(a) 上 a 出现 3 次
        string colors = "abaca";
        vector<vector<int>> edges = {{0, 1}, {0, 2}, {2, 3}, {3, 4}};
        expect_eq("官方例 1 abaca", sol.largestPathValue(colors, edges), 3);
    }
    {
        // 自环
        string colors = "a";
        vector<vector<int>> edges = {{0, 0}};
        expect_eq("官方例 2 自环", sol.largestPathValue(colors, edges), -1);
    }
    {
        // 两条平行边，路径 0->1 上 h 出现 2 次
        string colors = "hh";
        vector<vector<int>> edges = {{0, 1}, {0, 1}};
        expect_eq("官方例 3 重边", sol.largestPathValue(colors, edges), 2);
    }
    {
        // 单点无边
        string colors = "a";
        vector<vector<int>> edges;
        expect_eq("单点无边", sol.largestPathValue(colors, edges), 1);
    }
    {
        // 同色长链，整条路径 4 个 a
        string colors = "aaaa";
        vector<vector<int>> edges = {{0, 1}, {1, 2}, {2, 3}};
        expect_eq("同色长链", sol.largestPathValue(colors, edges), 4);
    }
    {
        // 三元环
        string colors = "abc";
        vector<vector<int>> edges = {{0, 1}, {1, 2}, {2, 0}};
        expect_eq("三元环", sol.largestPathValue(colors, edges), -1);
    }
    {
        // 不连通：两条边互不相干，最优只是单点颜色 1 次
        string colors = "ab";
        vector<vector<int>> edges;
        expect_eq("全孤立", sol.largestPathValue(colors, edges), 1);
    }
    {
        // 0 与 1 是兄弟分支，路径只能走其中一条：a 各出现 1 次，不可累加
        string colors = "aab";
        vector<vector<int>> edges = {{0, 2}, {1, 2}};
        expect_eq("兄弟分支不合并", sol.largestPathValue(colors, edges), 1);
    }
    {
        // 0->1->2 与 0->2 汇合于 2，必须取较大的那条（2 次 a）
        string colors = "aab";
        vector<vector<int>> edges = {{0, 1}, {1, 2}, {0, 2}};
        expect_eq("汇合取较大的前驱", sol.largestPathValue(colors, edges), 2);
    }
    {
        // 环与链并存，整体仍判 -1
        string colors = "abcd";
        vector<vector<int>> edges = {{0, 1}, {1, 2}, {2, 1}, {3, 0}};
        expect_eq("环链并存", sol.largestPathValue(colors, edges), -1);
    }

    // ---- 随机 DAG 对拍（只连 i<j，天然无环）----
    for (int iter = 0; iter < 500; ++iter) {
        const int n = 1 + static_cast<int>(next_rand() % 7);
        string colors(n, 'a');
        for (int i = 0; i < n; ++i) {
            colors[i] = static_cast<char>('a' + next_rand() % 3);
        }
        vector<vector<int>> edges;
        for (int i = 0; i < n; ++i) {
            for (int j = i + 1; j < n; ++j) {
                if (next_rand() % 3 == 0) {
                    edges.push_back({i, j});
                }
            }
        }
        expect_eq("随机 DAG", sol.largestPathValue(colors, edges), brute(colors, edges));
    }

    // ---- 随机一般图对拍（允许成环，含自环）----
    for (int iter = 0; iter < 500; ++iter) {
        const int n = 1 + static_cast<int>(next_rand() % 6);
        string colors(n, 'a');
        for (int i = 0; i < n; ++i) {
            colors[i] = static_cast<char>('a' + next_rand() % 3);
        }
        vector<vector<int>> edges;
        for (int i = 0; i < n; ++i) {
            for (int j = 0; j < n; ++j) {
                if (next_rand() % 5 == 0) {
                    edges.push_back({i, j});
                }
            }
        }
        expect_eq("随机一般图", sol.largestPathValue(colors, edges), brute(colors, edges));
    }

    if (g_failed != 0) {
        cout << "leetcode_1857: " << g_failed << " / " << g_cases << " cases failed\n";
        return 1;
    }
    cout << "leetcode_1857: all checks passed (" << g_cases << " cases)\n";
    return 0;
}
