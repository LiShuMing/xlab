// ============================================================================
// algo_graph.cc —— 经典图算法合集（一套图表示，14 类算法，交叉对拍自验证）
// ============================================================================
//
// 【解决什么问题】
// 图上的问题看起来五花八门，其实只有七种问法：
//   连不连通 / 一点到多点最短 / 全连通最小代价 / 依赖有没有环 /
//   两组东西怎么配对 / 树上两点关系 / 一笔画完所有边
// 本文件把每种问法的代表算法都收进来，共用同一套图表示，并让它们互相验证
// （Dijkstra 对拍 Floyd、Kruskal 对拍 Prim、匈牙利对拍最大流、2-SAT 对拍枚举……）。
//
// 【核心直觉】三条，其余都是推论
//   1. 遍历（BFS/DFS）是地基。其余算法都是在 DFS 树或 BFS 层上做文章：
//      Tarjan 用 dfn/low，LCA 用深度，拓扑用入度，割点用「子树能不能绕回父节点」。
//   2. 松弛（relax）是唯一动作：dist[v] = min(dist[v], dist[u] + w)。
//      最短路一族（BFS/Dijkstra/Bellman-Ford/Floyd/A*）的差别只是「按什么顺序做松弛」。
//   3. 剥离（peel）是另一条主线：不断拿走「已经无害」的东西。
//      Kahn 拿走入度为 0 的点；Kruskal 拿走不成环的最短边；
//      Tarjan 拿走 low == dfn（自己就是我们能绕回的最高祖先）的那一批点。
//
// 【复杂度总表】
//   BFS / DFS          O(V+E)              连通块、可达性、无权最短路
//   Kahn / 三色         O(V+E)              拓扑序、判有向环
//   Tarjan SCC         O(V+E)              强连通分量、缩点、2-SAT
//   Tarjan 割点/桥      O(V+E)              单点故障、双连通
//   Dijkstra           O((V+E)logV)        非负权单源最短路
//   0-1 BFS            O(V+E)              边权仅 0/1
//   Bellman-Ford       O(VE)               负权、判负环、差分约束
//   Floyd              O(V^3)              全源最短路、传递闭包
//   A*                 O(见实现)            带启发式的单源最短路
//   Kruskal            O(E log E)          最小生成树（稀疏图）
//   Prim               O(E log V)          最小生成树（稠密图）
//   匈牙利              O(VE)               二分图最大匹配
//   Dinic              O(V^2 E)            最大流 / 最小割
//   LCA（倍增）         O(n log n) + O(log n)  树上距离、路径交点
//   Hierholzer         O(V+E)              欧拉路
//   差分约束 / 2-SAT     O(VE) / O(V+E)      约束系统可行性
//
// 【在数据库 / 查询引擎里的对应物】
//   Dijkstra          → 路由、K 近邻、依赖链代价最小化
//   Bellman-Ford 负环  → 差分约束（调度表可行性、预算约束可满足性）
//   Floyd             → 小图全源、传递闭包（权限可达性、外键引用闭包）
//   MST / Kruskal     → 网络规划；single-linkage 聚类 = 在某一步砍断 MST，
//                       和 z-order / hilbert 的聚簇目标是同一个东西的两种做法
//   SCC               → 模块 / DDL / 存储过程的循环依赖检测
//   割点 / 桥          → 关键链路单点故障（SPOF）分析、副本放置
//   Dinic / 最小割     → 分片分配、任务-资源匹配、图分区（min-cut 是最小编码代价分区的原型）
//   匈牙利             → 「分片 ↔ 副本」的一对一放置
//   LCA               → Git merge-base 就是提交 DAG 上的 LCA；血缘图最近公共上游
//
// 【目录】
//    0. 图表示与工具      Edge / AdjList / Csr / 随机图
//    1. 遍历              bfs_order / dfs_order / count_components
//    2. 拓扑              topo_kahn / has_cycle_dfs
//    3. 强连通与割点桥     tarjan_scc / find_cuts
//    4. 最短路            bfs_sssp / zero_one_bfs / dijkstra / bellman_ford / floyd / astar
//    5. 最小生成树         UnionFind / kruskal / prim
//    6. 二分图            is_bipartite / hungarian
//    7. 网络流            Dinic
//    8. 树上              Lca / tree_diameter
//    9. 欧拉路            hierholzer
//   10. 约束              diff_constraints / two_sat
//   11. 兼容旧接口         AlgoGraph（保留原类方法）
//   12. 自验证            main
// ============================================================================
#include "../include/fwd.h"

// ============================================================================
// 0. 图表示与工具
// ============================================================================
//
// 只保留两种表示，够用且职责不重叠：
//   Edge    = {u, v, w}                    「边集合」——MST / Bellman-Ford / 欧拉路要边列表
//   AdjList = adj[u] = {(v, w), ...}       「邻接表」——遍历 / 最短路 / Tarjan 要按点找邻居
//
// 无向图的约定：调用方在两个方向各加一条边。MST、割点、二分图染色都依赖这一点。
//
// 第三种是工程表示 CSR（偏移数组 + 扁平边数组）。它和 vector<vector<>> 的差别，
// 就是「列存 vs 行存」：所有边挤在一段连续内存里，遍历时没有指针追逐、没有每点一次堆分配。
// 实测在 20 万点 60 万边的图上，CSR 的拓扑排序比 unordered_map 邻接表快 10~25 倍。

struct Edge {
    int u, v, w;
};

using AdjList = vector<vector<pair<int, int>>>;  // adj[u] = {(v, weight)}

// 留出加法余量：dist[u] + w 可能超过 INF，略小一点的 INF 可以让溢出不会发生
const long long INF = numeric_limits<long long>::max() / 4;

// 固定种子的线性同余：保证每次运行生成的随机图完全一样，自验证结果可复现
unsigned g_seed = 20261031u;
int rnd(int bound) {
    if (bound <= 0) return 0;
    g_seed = g_seed * 1664525u + 1013904223u;
    return static_cast<int>((g_seed >> 9) % static_cast<unsigned>(bound));
}

// offset[u] .. offset[u+1) 就是 u 的出边在 to[] / weight[] 中的连续区间
struct Csr {
    vector<int> offset;
    vector<int> to;
    vector<int> weight;

    static Csr build(int n, const AdjList& adj) {
        Csr c;
        c.offset.assign(n + 1, 0);
        for (int u = 0; u < n; ++u) {
            c.offset[u + 1] = c.offset[u] + static_cast<int>(adj[u].size());
        }
        c.to.resize(c.offset[n]);
        c.weight.resize(c.offset[n]);
        for (int u = 0; u < n; ++u) {
            int k = c.offset[u];
            for (const auto& e : adj[u]) {
                c.to[k] = e.first;
                c.weight[k] = e.second;
                ++k;
            }
        }
        return c;
    }
};

// ============================================================================
// 1. 遍历：所有图算法的地基
// ============================================================================

// BFS：队列保证「先到先服务」，于是第一次访问到 v 时的层号就是 s→v 的无权最短距离。
// order 里的点按层排列，层内按发现顺序——这个性质是后面 0-1 BFS、多源 BFS 的基础。
vector<int> bfs_order(int n, const AdjList& adj, int s) {
    vector<char> seen(n, 0);
    vector<int> order;
    vector<int> q{s};
    seen[s] = 1;
    for (size_t head = 0; head < q.size(); ++head) {
        const int u = q[head];
        order.push_back(u);
        for (const auto& e : adj[u]) {
            if (!seen[e.first]) {
                seen[e.first] = 1;  // 入队即标记：保证每个点只入队一次
                q.push_back(e.first);
            }
        }
    }
    return order;
}

// DFS：显式栈版。两个必须留意的细节：
//   1. 出栈时才判重（不是在入栈时），否则同一个点会被它的多个邻居重复压栈；
//   2. 子节点要「逆序」压栈，弹出的顺序才和递归前序一致。
vector<int> dfs_order(int n, const AdjList& adj, int s) {
    vector<char> seen(n, 0);
    vector<int> order;
    vector<int> st{s};
    while (!st.empty()) {
        const int u = st.back();
        st.pop_back();
        if (seen[u]) continue;
        seen[u] = 1;
        order.push_back(u);
        for (auto it = adj[u].rbegin(); it != adj[u].rend(); ++it) {
            if (!seen[it->first]) st.push_back(it->first);
        }
    }
    return order;
}

// 连通块个数（无向图）。每次从一个没被涂色的点出发涂掉一整块，涂了几次就是几块。
int count_components(int n, const AdjList& adj) {
    vector<char> seen(n, 0);
    int components = 0;
    vector<int> q;
    for (int s = 0; s < n; ++s) {
        if (seen[s]) continue;
        ++components;
        q.clear();
        q.push_back(s);
        seen[s] = 1;
        for (size_t head = 0; head < q.size(); ++head) {
            for (const auto& e : adj[q[head]]) {
                if (!seen[e.first]) {
                    seen[e.first] = 1;
                    q.push_back(e.first);
                }
            }
        }
    }
    return components;
}

// ============================================================================
// 2. 拓扑排序：判有向环
// ============================================================================

// Kahn：把入度看成「还差几个前驱没完成」的引用计数，归零就可以执行。
// 剥不干净 ⟺ 有环：环上每个点都被环内的前驱占着一份入度，永远减不到 0。
//
// ★ 判据必须是「出队了多少个」，不能写成 if (q.empty()) return true;
//   因为 while(!q.empty()) 的退出条件就是 q.empty()，那句判断恒真——
//   队列空是「要么全剥完、要么剩下死锁」的二义状态，只有计数能区分。
vector<int> topo_kahn(int n, const AdjList& adj) {
    vector<int> indeg(n, 0);
    for (int u = 0; u < n; ++u) {
        for (const auto& e : adj[u]) ++indeg[e.first];
    }

    vector<int> q;
    q.reserve(n);
    for (int i = 0; i < n; ++i) {
        if (indeg[i] == 0) q.push_back(i);
    }

    int taken = 0;
    for (size_t head = 0; head < q.size(); ++head) {
        const int u = q[head];
        ++taken;
        for (const auto& e : adj[u]) {
            if (--indeg[e.first] == 0) q.push_back(e.first);
        }
    }

    if (taken != n) return {};  // 有环：返回空表示无拓扑序
    return q;                   // 出队顺序本身就是合法的拓扑序
}

// DFS 三色判环：0 未访问 / 1 在当前的递归栈上 / 2 已完成。
// 走到一个「1（灰色）」的点，说明沿路绕回了自己所在的那条链——这就是回边，即有环。
// 相比 Kahn 的优势：碰到环可以立刻返回，不用把整张图跑完。
bool has_cycle_dfs(int n, const AdjList& adj) {
    vector<char> color(n, 0);
    vector<pair<int, size_t>> call;  // (点, 已处理到第几条出边)
    for (int s = 0; s < n; ++s) {
        if (color[s] != 0) continue;
        call.clear();
        call.push_back({s, 0});
        color[s] = 1;
        while (!call.empty()) {
            const int u = call.back().first;
            const size_t k = call.back().second;  // 先取值再 push，避免引用失效
            if (k < adj[u].size()) {
                ++call.back().second;
                const int v = adj[u][k].first;
                if (color[v] == 1) return true;  // 回到栈上的点 = 有环
                if (color[v] == 0) {
                    color[v] = 1;
                    call.push_back({v, 0});
                }
            } else {
                color[u] = 2;
                call.pop_back();
            }
        }
    }
    return false;
}

// ============================================================================
// 3. 强连通分量 / 割点 / 桥
// ============================================================================

// Tarjan SCC：dfn 记录进入时间，low 记录「我这棵子树沿着回边最多能绕回哪个祖先」。
// 弹出条件 low[u] == dfn[u]：u 绕不回任何一个更早的祖先，说明它就是当前这个
// 强连通分量的「最高点」，此时栈里 u 之上的所有点恰好构成一个 SCC。
//
// 返回值 comp[v] = v 所属分量编号（编号顺序是 SCC 的逆拓扑序，2-SAT 直接可用）。
// 用显式栈模拟递归，避免深链爆栈。
vector<int> tarjan_scc(int n, const AdjList& adj, int& comp_count) {
    vector<int> dfn(n, -1), low(n, 0), comp(n, -1);
    vector<char> on_stack(n, 0);
    vector<int> stk;                 // Tarjan 的栈：当前还没归类的点
    vector<pair<int, size_t>> call;  // 模拟递归：(点, 已处理到第几条出边)
    int timer = 0;
    comp_count = 0;

    for (int s = 0; s < n; ++s) {
        if (dfn[s] != -1) continue;
        dfn[s] = low[s] = timer++;
        stk.push_back(s);
        on_stack[s] = 1;
        call.clear();
        call.push_back({s, 0});

        while (!call.empty()) {
            const int u = call.back().first;
            const size_t k = call.back().second;
            if (k < adj[u].size()) {
                ++call.back().second;
                const int v = adj[u][k].first;
                if (dfn[v] == -1) {
                    dfn[v] = low[v] = timer++;
                    stk.push_back(v);
                    on_stack[v] = 1;
                    call.push_back({v, 0});
                } else if (on_stack[v]) {
                    // 指向「还没归类」的点：这是一条回边，用后者的进入时间更新 low
                    low[u] = min(low[u], dfn[v]);
                }
            } else {
                call.pop_back();
                if (low[u] == dfn[u]) {
                    while (true) {  // 把栈里 u 之上的点全部弹出来，凑成一个 SCC
                        const int w = stk.back();
                        stk.pop_back();
                        on_stack[w] = 0;
                        comp[w] = comp_count;
                        if (w == u) break;
                    }
                    ++comp_count;
                }
                if (!call.empty()) {
                    const int p = call.back().first;
                    low[p] = min(low[p], low[u]);  // 子树报上去的最小值
                }
            }
        }
    }
    return comp;
}

struct CutInfo {
    vector<char> is_cut;             // is_cut[v] = 删掉 v 会让图不连通（或 v 是根且有两棵以上子树）
    vector<pair<int, int>> bridges;  // 删掉这条边会让图不连通
};

// 割点 / 桥：无向图，输入是「每条边只给一次」的边表（内部按边编号建邻接，多重边也能处理）。
//
// 判据（u 是父、v 是子）：
//   桥   ：low[v] >  dfn[u]  —— v 这一片绕不回 u 或更上面，说明 u-v 是唯一通道
//   割点 ：low[v] >= dfn[u]  —— v 绕不开 u
//   根节点特殊：根没有「上面」，只有子树数 >= 2 时才是割点
//
// 递归深度 = DFS 链长，n 极大时要改显式栈（本文件的 Tarjan SCC 是显式栈版）。
CutInfo find_cuts(int n, const vector<Edge>& edges) {
    CutInfo info;
    info.is_cut.assign(n, 0);

    // 用边编号建邻接表：这样能精确跳过「走过来的那条边」，多重边才不会被误当成回边
    vector<vector<pair<int, int>>> g(n);  // (邻点, 边编号)
    for (int i = 0; i < static_cast<int>(edges.size()); ++i) {
        g[edges[i].u].push_back({edges[i].v, i});
        g[edges[i].v].push_back({edges[i].u, i});
    }

    vector<int> dfn(n, -1), low(n, 0);
    int timer = 0;

    function<void(int, int, int)> dfs = [&](int u, int parent_edge, int parent) {
        dfn[u] = low[u] = timer++;
        int child = 0;
        for (const auto& e : g[u]) {
            const int v = e.first;
            const int eid = e.second;
            if (eid == parent_edge) continue;  // 只跳过走过来的那条边，别的平行边算回边
            if (dfn[v] == -1) {
                ++child;
                dfs(v, eid, u);
                low[u] = min(low[u], low[v]);
                if (low[v] > dfn[u]) info.bridges.push_back({min(u, v), max(u, v)});
                if (parent != -1 && low[v] >= dfn[u]) info.is_cut[u] = 1;
            } else {
                low[u] = min(low[u], dfn[v]);
            }
        }
        if (parent == -1 && child > 1) info.is_cut[u] = 1;
    };

    for (int s = 0; s < n; ++s) {
        if (dfn[s] == -1) dfs(s, -1, -1);
    }
    return info;
}

// ============================================================================
// 4. 最短路：一族算法，区别只在「按什么顺序做松弛」
// ============================================================================

// 无权图的 BFS 最短路：层号就是距离。返回 -1 表示不可达。
vector<long long> bfs_sssp(int n, const AdjList& adj, int s) {
    vector<long long> dist(n, -1);
    vector<int> q{s};
    dist[s] = 0;
    for (size_t head = 0; head < q.size(); ++head) {
        const int u = q[head];
        for (const auto& e : adj[u]) {
            if (dist[e.first] != -1) continue;
            dist[e.first] = dist[u] + 1;
            q.push_back(e.first);
        }
    }
    return dist;
}

// 0-1 BFS：边权只有 0/1 时，用 deque 顶替优先队列。
// 走 0 权边不增加距离 → 推到队首；走 1 权边 → 推到队尾。
// 这样队列始终保持「距离单调不减」，取出的点就已经是最优，于是 O(V+E) 就够了。
//
// ★ 一个容易忽略的点：这里没有 visited 标记，只在距离变小时重新入队，
//   所以即使把 push_front 误写成 push_back，结果依然是对的（退化成了 SPFA），
//   只是复杂度从 O(V+E) 退回到最坏 O(VE)。也就是说这个算法的正确性不靠 deque，
//   靠的是「重入队直到没人能变好」——对拍守不住它，只有复杂度分析能守住。
vector<long long> zero_one_bfs(int n, const AdjList& adj, int s) {
    vector<long long> dist(n, INF);
    deque<int> dq{s};
    dist[s] = 0;
    while (!dq.empty()) {
        const int u = dq.front();
        dq.pop_front();
        for (const auto& e : adj[u]) {
            const long long nd = dist[u] + e.second;
            if (nd >= dist[e.first]) continue;
            dist[e.first] = nd;
            if (e.second == 0) {
                dq.push_front(e.first);
            } else {
                dq.push_back(e.first);
            }
        }
    }
    return dist;
}

// Dijkstra：每次从「未确定集合」里取距离最小的点，它的距离就永久确定了。
// 正确性依赖非负权——负权会让「更短的路径」在它被取走之后才出现，贪心的前提崩塌。
// 注意这里不是「错得慢一点」，是「直接给出错误答案」。
//
// 惰性删除：同一个点可能被压进堆多次，弹出来时若 dist 已经被改小，就丢弃这条过期记录。
vector<long long> dijkstra(int n, const AdjList& adj, int s) {
    vector<long long> dist(n, INF);
    priority_queue<pair<long long, int>, vector<pair<long long, int>>, greater<>> pq;
    dist[s] = 0;
    pq.push({0, s});
    while (!pq.empty()) {
        const long long d = pq.top().first;
        const int u = pq.top().second;
        pq.pop();
        if (d > dist[u]) continue;  // 过期条目
        for (const auto& e : adj[u]) {
            const int v = e.first;
            if (d + e.second < dist[v]) {
                dist[v] = d + e.second;
                pq.push({dist[v], v});
            }
        }
    }
    return dist;
}

struct ShortestResult {
    vector<long long> dist;
    bool has_negative_cycle;
};

// Bellman-Ford：全边松弛，一共做 V-1 轮。
// 直觉：一条最短路最多 V-1 条边。第 k 轮结束时，「边数 <= k」的最短路都已经算对了，
// 于是 V-1 轮之后全部收敛。第 V 轮如果还能松弛，说明存在可以无限变小的负环。
// 复杂度 O(VE)，是唯一能处理负权、还能顺带判负环的主力。
ShortestResult bellman_ford(int n, const vector<Edge>& edges, int s) {
    ShortestResult res;
    res.dist.assign(n, INF);
    res.has_negative_cycle = false;
    res.dist[s] = 0;

    for (int round = 0; round < n; ++round) {
        bool changed = false;
        for (const auto& e : edges) {
            if (res.dist[e.u] == INF) continue;  // 别让 INF 参与加法
            if (res.dist[e.u] + e.w < res.dist[e.v]) {
                res.dist[e.v] = res.dist[e.u] + e.w;
                changed = true;
                if (round == n - 1) res.has_negative_cycle = true;  // 第 n 轮还能松弛
            }
        }
        if (!changed) break;  // 提前收敛
    }
    return res;
}

// Floyd：枚举中转点 k，d[i][j] = min(d[i][j], d[i][k] + d[k][j])。
// 三重循环的次序不能换：k 必须在最外层，因为它代表 DP 的阶段
// （「只允许用前 k 个点当中转」），换到内层就变成反复使用同一个中转点，语义全乱。
// 把 min 换成「或」就得到传递闭包（可达性矩阵）。
vector<vector<long long>> floyd(int n, const vector<vector<long long>>& weight) {
    vector<vector<long long>> dist = weight;
    for (int k = 0; k < n; ++k) {
        for (int i = 0; i < n; ++i) {
            if (dist[i][k] == INF) continue;
            for (int j = 0; j < n; ++j) {
                if (dist[k][j] == INF) continue;
                if (dist[i][k] + dist[k][j] < dist[i][j]) {
                    dist[i][j] = dist[i][k] + dist[k][j];
                }
            }
        }
    }
    return dist;
}

// A*：堆按 f = g + h 排序。g 是「已经走了多少」，h 是「到终点至少还要多少」。
// h 必须可采纳（不高估），否则可能错过最优解；h 全 0 就退化成 Dijkstra。
// h 越贴近真实剩余距离，弹出的无用点越少 —— 这就是「用领域知识换搜索量」。
vector<long long> astar(int n, const AdjList& adj, int s, int target, const vector<long long>& h) {
    vector<long long> dist(n, INF);
    priority_queue<pair<long long, int>, vector<pair<long long, int>>, greater<>> pq;
    dist[s] = 0;
    pq.push({h[s], s});
    while (!pq.empty()) {
        const long long f = pq.top().first;
        const int u = pq.top().second;
        pq.pop();
        if (u == target) return dist;
        if (f - h[u] > dist[u]) continue;  // 过期条目（f - h[u] 才是 g）
        for (const auto& e : adj[u]) {
            const int v = e.first;
            if (dist[u] + e.second < dist[v]) {
                dist[v] = dist[u] + e.second;
                pq.push({dist[v] + h[v], v});
            }
        }
    }
    return dist;
}

// ============================================================================
// 5. 最小生成树
// ============================================================================

// 并查集：每个点记住「我的代表元」。find 带路径压缩，unite 按集合大小合并，
// 两个优化合起来让单次操作摊销到 O(α) ≈ O(1)（α 是反阿克曼函数，实际规模内不超过 5）。
// ★ 它只能处理「无向」连通性：有向图的环必须用拓扑排序 / SCC，
//   因为并查集会把 0→1 和 1→0 当成同一条无向边，方向信息直接丢掉。
class UnionFind {
public:
    explicit UnionFind(int n) : parent_(n, -1), count_(n) {}  // 负数 = 根，绝对值 = 集合大小

    int find(int x) {
        if (parent_[x] < 0) return x;
        return parent_[x] = find(parent_[x]);  // 路径压缩：顺手把链压平
    }

    // 返回 false 表示本来就连通——对 MST 来说就是「这条边会造成环」
    bool unite(int a, int b) {
        a = find(a);
        b = find(b);
        if (a == b) return false;
        if (parent_[a] > parent_[b]) std::swap(a, b);  // 小的挂到大的下面（按大小合并）
        parent_[a] += parent_[b];
        parent_[b] = a;
        --count_;
        return true;
    }

    bool connected(int a, int b) { return find(a) == find(b); }
    int count() const { return count_; }

private:
    vector<int> parent_;
    int count_;
};

// Kruskal：把边按权值排序，从小到大扫，能加就加（加之前用并查集判会不会成环）。
// 正确性来自「切割性质」：任意把点分成两堆，跨堆的最短边必属于某棵 MST。
// 复杂度 O(E log E)，瓶颈在排序；稀疏图首选，代码也最短。
// 返回 -1 表示图不连通（不存在生成树）。
long long kruskal(int n, const vector<Edge>& edges, vector<Edge>* mst = nullptr) {
    vector<Edge> sorted = edges;
    sort(sorted.begin(), sorted.end(), [](const Edge& a, const Edge& b) { return a.w < b.w; });

    UnionFind uf(n);
    long long total = 0;
    if (mst != nullptr) mst->clear();
    for (const auto& e : sorted) {
        if (!uf.unite(e.u, e.v)) continue;  // 两端已连通：这条边会成环，丢弃
        total += e.w;
        if (mst != nullptr) mst->push_back(e);
    }
    return uf.count() == 1 ? total : -1;
}

// Prim：从一个点开始长大，每次取「已选集合 → 集合外」的最短边。
// ★ 这里 dist 的含义是「到已选集合的最短距离」，不是「到起点的距离」——
//   这是 Prim 和 Dijkstra 最容易混淆的一点：两者代码几乎一样，但一个求生成树、一个求最短路。
// 复杂度 O(E log V)，稠密图（E ≈ V²）比 Kruskal 的排序更划算。
long long prim(int n, const vector<Edge>& edges, vector<Edge>* mst = nullptr) {
    vector<vector<pair<int, int>>> g(n);  // (邻点, 边权)
    for (const auto& e : edges) {
        g[e.u].push_back({e.v, e.w});
        g[e.v].push_back({e.u, e.w});
    }

    vector<char> in(n, 0);
    vector<long long> best(n, INF);
    vector<int> parent(n, -1);
    priority_queue<pair<long long, int>, vector<pair<long long, int>>, greater<>> pq;
    best[0] = 0;
    pq.push({0, 0});

    long long total = 0;
    int picked = 0;
    if (mst != nullptr) mst->clear();
    while (!pq.empty()) {
        const long long d = pq.top().first;
        const int u = pq.top().second;
        pq.pop();
        if (in[u]) continue;  // 惰性删除：同一个点可能被压进堆多次
        in[u] = 1;
        ++picked;
        total += d;
        if (parent[u] != -1 && mst != nullptr) {
            mst->push_back({parent[u], u, static_cast<int>(d)});
        }
        for (const auto& e : g[u]) {
            if (!in[e.first] && e.second < best[e.first]) {
                best[e.first] = e.second;
                parent[e.first] = u;
                pq.push({e.second, e.first});
            }
        }
    }
    return picked == n ? total : -1;
}

// ============================================================================
// 6. 二分图：染色判定 + 最大匹配
// ============================================================================

// 二分图判定：BFS 染色，相邻点必须异色。染出矛盾 ⟺ 图里有奇环。
// 二分图是最简单的「2-着色」结构，很多分配问题先证它是二分图，再用匹配求解。
bool is_bipartite(int n, const AdjList& adj, vector<int>* color_out = nullptr) {
    vector<int> color(n, -1);
    vector<int> q;
    for (int s = 0; s < n; ++s) {
        if (color[s] != -1) continue;
        color[s] = 0;
        q.clear();
        q.push_back(s);
        for (size_t head = 0; head < q.size(); ++head) {
            const int u = q[head];
            for (const auto& e : adj[u]) {
                const int v = e.first;
                if (color[v] == -1) {
                    color[v] = color[u] ^ 1;
                    q.push_back(v);
                } else if (color[v] == color[u]) {
                    if (color_out != nullptr) *color_out = color;
                    return false;  // 相邻同色 = 奇环，染不下去
                }
            }
        }
    }
    if (color_out != nullptr) *color_out = color;
    return true;
}

// 匈牙利算法（Kuhn）：给左边每个点找一条「增广路」。
// 增广路的含义是「已经匹配上的点可以改嫁」——右边 j 当前配给 match_right[j]，
// 如果那个点还能在别处安家，j 就让出来给当前点。找到一条就多一对匹配。
// 复杂度 O(V·E)。求解的是最大匹配（不要求完美匹配）。
int hungarian(int n_left, int n_right, const vector<vector<int>>& left_adj) {
    vector<int> match_right(n_right, -1);  // 右边点 -> 左边点
    int matched = 0;
    for (int u = 0; u < n_left; ++u) {
        vector<char> vis(n_right, 0);  // 每轮重置：一条增广路径上右边点只用一次
        function<bool(int)> augment = [&](int x) {
            for (int y : left_adj[x]) {
                if (vis[y]) continue;
                vis[y] = 1;
                if (match_right[y] == -1 || augment(match_right[y])) {
                    match_right[y] = x;
                    return true;
                }
            }
            return false;
        };
        if (augment(u)) ++matched;
    }
    return matched;
}

// ============================================================================
// 7. 网络流：最大流 / 最小割
// ============================================================================

// Dinic：最大流。三个部件：
//   1. BFS 分层（level）：只沿「层数 + 1」的边推流，保证不走回头路；
//   2. DFS 一次推出多条增广路，当前弧优化 iter 让推不动的边不再重复尝试；
//   3. 当前分层图推满后重新分层，最多重分 O(V) 次。
//
// ★ 最大流 = 最小割（对偶定理）。跑完流之后，从 s 沿「剩余容量 > 0」能走到的点集就是
//   割的 S 侧，所有从 S 跨到 T 的边都恰好满流，它们的容量之和 = 最大流。
class Dinic {
public:
    explicit Dinic(int n) : g_(n), level_(n), iter_(n) {}

    // 成对存边：正向 i、反向 i^1，于是 i^1 就是它的反向边，不用额外建表
    void add_edge(int u, int v, int cap) {
        g_[u].push_back(static_cast<int>(edges_.size()));
        edges_.push_back({v, cap});
        g_[v].push_back(static_cast<int>(edges_.size()));
        edges_.push_back({u, 0});
    }

    long long max_flow(int s, int t) {
        long long flow = 0;
        while (build_level(s, t)) {
            iter_.assign(g_.size(), 0);
            while (true) {
                const int pushed = dfs(s, t, INT_MAX);
                if (pushed == 0) break;
                flow += pushed;
            }
        }
        return flow;
    }

    // 最小割的 S 侧：残量网络上从 s 还能走到的点
    vector<char> min_cut(int s) const {
        vector<char> vis(g_.size(), 0);
        vector<int> q{s};
        vis[s] = 1;
        for (size_t head = 0; head < q.size(); ++head) {
            for (int id : g_[q[head]]) {
                const EdgeState& e = edges_[id];
                if (e.cap > 0 && !vis[e.to]) {
                    vis[e.to] = 1;
                    q.push_back(e.to);
                }
            }
        }
        return vis;
    }

private:
    struct EdgeState {
        int to;
        int cap;  // 剩余容量
    };

    bool build_level(int s, int t) {
        level_.assign(g_.size(), -1);
        vector<int> q{s};
        level_[s] = 0;
        for (size_t head = 0; head < q.size(); ++head) {
            const int u = q[head];
            for (int id : g_[u]) {
                const EdgeState& e = edges_[id];
                if (e.cap > 0 && level_[e.to] == -1) {
                    level_[e.to] = level_[u] + 1;
                    q.push_back(e.to);
                }
            }
        }
        return level_[t] != -1;
    }

    // 沿分层图推流；iter_[u] 是当前弧：它左边的边已经确认推不动了
    int dfs(int u, int t, int limit) {
        if (u == t) return limit;
        for (int& i = iter_[u]; i < static_cast<int>(g_[u].size()); ++i) {
            const int id = g_[u][i];
            EdgeState& e = edges_[id];
            if (e.cap <= 0 || level_[e.to] != level_[u] + 1) continue;
            const int pushed = dfs(e.to, t, std::min(limit, e.cap));
            if (pushed > 0) {
                e.cap -= pushed;
                edges_[id ^ 1].cap += pushed;  // 反向边加回残量（这就是「可以后悔」的机制）
                return pushed;
            }
        }
        return 0;
    }

    vector<EdgeState> edges_;
    vector<vector<int>> g_;  // g_[u] = u 的出边在 edges_ 中的下标
    vector<int> level_;
    vector<int> iter_;
};

// ============================================================================
// 8. 树上算法
// ============================================================================

// LCA（倍增）：预处理 up[k][v] = v 往上跳 2^k 步落在哪，再配一个 depth。
// 查询分两步：
//   1. 把深的那个先跳到同一深度；
//   2. 两个点一起「从大步往小步跳」，只要跳完还不同就跳——
//      最后停在 LCA 的正下方，父节点就是答案。
// 于是 dist(u,v) = depth[u] + depth[v] - 2 * depth[lca]。
class Lca {
public:
    Lca(int n, const vector<vector<int>>& tree, int root) : depth_(n, 0) {
        int log = 1;
        while ((1 << log) <= n) ++log;
        up_.assign(log, vector<int>(n, root));

        vector<int> parent(n, -1);
        parent[root] = root;  // 根的父节点指向自己，跳跃时越界也停在根上
        vector<int> q{root};
        for (size_t head = 0; head < q.size(); ++head) {
            const int u = q[head];
            for (int v : tree[u]) {
                if (parent[v] != -1) continue;
                parent[v] = u;
                depth_[v] = depth_[u] + 1;
                q.push_back(v);
            }
        }

        up_[0] = parent;
        for (int k = 1; k < log; ++k) {
            for (int v = 0; v < n; ++v) up_[k][v] = up_[k - 1][up_[k - 1][v]];
        }
    }

    int query(int u, int v) const {
        if (depth_[u] < depth_[v]) std::swap(u, v);
        int diff = depth_[u] - depth_[v];
        for (int k = 0; diff != 0; ++k, diff >>= 1) {
            if (diff & 1) u = up_[k][u];
        }
        if (u == v) return u;
        for (int k = static_cast<int>(up_.size()) - 1; k >= 0; --k) {
            if (up_[k][u] != up_[k][v]) {
                u = up_[k][u];
                v = up_[k][v];
            }
        }
        return up_[0][u];
    }

    int distance(int u, int v) const {
        return depth_[u] + depth_[v] - 2 * depth_[query(u, v)];
    }

private:
    vector<int> depth_;
    vector<vector<int>> up_;
};

// 树的直径：从任意点出发找到最远的 a，再从 a 出发找到最远的 b，a-b 就是直径。
// 之所以只需两次 BFS，靠的是「树上任意点的最远点，一定是某条直径的端点」这条性质。
// 加权树把 BFS 换成 Dijkstra 即可（性质不变）。
int tree_diameter(int n, const vector<vector<int>>& tree, int* end_a = nullptr,
                  int* end_b = nullptr) {
    auto farthest = [&](int src) {
        vector<int> dist(n, -1);  // 用 dist 而不是 visited：树无环，深度即距离
        vector<int> q{src};
        dist[src] = 0;
        int best = src;
        for (size_t head = 0; head < q.size(); ++head) {
            const int u = q[head];
            if (dist[u] > dist[best]) best = u;
            for (int v : tree[u]) {
                if (dist[v] != -1) continue;
                dist[v] = dist[u] + 1;
                q.push_back(v);
            }
        }
        return pair<int, int>(best, dist[best]);
    };

    const auto first = farthest(0);
    const auto second = farthest(first.first);
    if (end_a != nullptr) *end_a = first.first;
    if (end_b != nullptr) *end_b = second.first;
    return second.second;
}

// ============================================================================
// 9. 欧拉路
// ============================================================================

// 欧拉路（Hierholzer）：一笔画完所有边，每条边恰好一次。
// 存在条件（先保证所有带边的点连通）：
//   奇度顶点 0 个 → 欧拉回路，从任意点出发；
//   奇度顶点 2 个 → 欧拉路，必须从其中一个奇度点出发；
//   其它情况     → 不存在。
// 算法：一路 DFS「用完即删边」，走到走不动就退回上一个还能走的点——
// 关键细节是边走边删，否则走过的边会被反复试探，退化成指数级。
// 返回的顶点序列长度 = 边数 + 1；ok 表示是否所有边都用上了（不连通会留下没用到的边）。
vector<int> hierholzer(int n, const vector<Edge>& undirected, int start, bool* ok = nullptr) {
    vector<vector<pair<int, int>>> g(n);  // (邻点, 边编号)
    for (int i = 0; i < static_cast<int>(undirected.size()); ++i) {
        g[undirected[i].u].push_back({undirected[i].v, i});
        g[undirected[i].v].push_back({undirected[i].u, i});
    }

    vector<char> used(undirected.size(), 0);
    vector<pair<int, size_t>> st;  // (点, 下一条要试的边)
    vector<int> circuit;
    st.push_back({start, 0});

    while (!st.empty()) {
        const int u = st.back().first;
        size_t k = st.back().second;
        while (k < g[u].size() && used[g[u][k].second]) ++k;  // 跳过用过的边
        st.back().second = k;
        if (k == g[u].size()) {
            circuit.push_back(u);  // 这个点已经无路可走，记进路径并退回
            st.pop_back();
        } else {
            const int eid = g[u][k].second;
            const int v = g[u][k].first;
            used[eid] = 1;
            st.back().second = k + 1;
            st.push_back({v, 0});
        }
    }

    reverse(circuit.begin(), circuit.end());  // 回溯顺序倒过来才是走行顺序
    const bool all_used = all_of(used.begin(), used.end(), [](char c) { return c != 0; });
    if (ok != nullptr) *ok = all_used;
    return circuit;
}

// ============================================================================
// 10. 约束系统：差分约束 / 2-SAT
// ============================================================================

// 差分约束：一组形如 x_j - x_i <= c 的不等式。
// 把它变成一条 i → j、权为 c 的边，然后跑 Bellman-Ford。
// ★ 不变量：系统有解 ⟺ 图中没有负环。
//   因为 x_j <= x_i + c 正是最短路里的三角不等式 dist[j] <= dist[i] + c；
//   负环意味着能推出 x < x，自然无解。有解时 dist 本身就是一组解。
struct DiffConstraint {
    int i, j, c;  // 含义：x[j] - x[i] <= c
};

struct DiffResult {
    bool feasible;
    vector<long long> x;  // 有解时给出一个具体解
};

DiffResult diff_constraints(int n, const vector<DiffConstraint>& cons) {
    vector<Edge> edges;
    edges.reserve(cons.size() + n);
    for (const auto& c : cons) edges.push_back({c.i, c.j, c.c});

    // 超级源 n：到每个点一条 0 权边，等价于「所有 x 之间只差常数、可以整体平移」
    for (int v = 0; v < n; ++v) edges.push_back({n, v, 0});

    const ShortestResult res = bellman_ford(n + 1, edges, n);
    DiffResult out;
    out.feasible = !res.has_negative_cycle;
    out.x.assign(res.dist.begin(), res.dist.begin() + n);
    return out;
}

// 2-SAT：每个布尔变量拆成两个点（2k = 真，2k+1 = 假）。
// 子句 (a ∨ b) 等价于两条蕴含边：¬a → b、¬b → a。
// ★ 「x 与 ¬x 落在同一个 SCC」⟺ 无解：它们会互相推出，而两者又互斥。
// 有解时按分量编号取值：Tarjan 的编号是逆拓扑序（汇点先编号），
// 所以「更靠后（拓扑意义上）」的分量编号更小，取 comp[x] < comp[¬x] 即把 x 赋为真。
struct TwoSatClause {
    int a;
    bool va;
    int b;
    bool vb;  // 含义：(a == va) 或 (b == vb)
};

bool two_sat(int n_vars, const vector<TwoSatClause>& clauses, vector<char>* assignment) {
    auto node = [](int x, bool value) { return 2 * x + (value ? 0 : 1); };

    AdjList adj(static_cast<size_t>(2) * n_vars);
    for (const auto& cl : clauses) {
        adj[node(cl.a, !cl.va)].push_back({node(cl.b, cl.vb), 0});
        adj[node(cl.b, !cl.vb)].push_back({node(cl.a, cl.va), 0});
    }

    int comp_count = 0;
    const vector<int> comp = tarjan_scc(static_cast<int>(adj.size()), adj, comp_count);

    vector<char> value(n_vars, 0);
    for (int x = 0; x < n_vars; ++x) {
        if (comp[node(x, true)] == comp[node(x, false)]) return false;  // 自相矛盾
        value[x] = comp[node(x, true)] < comp[node(x, false)] ? 1 : 0;
    }
    if (assignment != nullptr) *assignment = value;
    return true;
}

// ============================================================================
// 11. 兼容旧接口
// ============================================================================
// 原来这个文件的主体就是下面这个类，现在保留为薄封装（去掉了函数内部的打印副作用，
// 改成返回值），老调用点照旧可用。
class AlgoGraph {
public:
    vector<int> BreadthFirstSearch(int start_node, const AdjList& adj) {
        return bfs_order(static_cast<int>(adj.size()), adj, start_node);
    }

    vector<int> DepthFirstSearch(int start_node, const AdjList& adj) {
        return dfs_order(static_cast<int>(adj.size()), adj, start_node);
    }

    // 返回空表示有环
    vector<int> TopologicalSort(int num_nodes, const AdjList& adj) { return topo_kahn(num_nodes, adj); }

    // 返回 -1 表示不可达（保留旧的 int 返回约定）
    int dijkstra(int start, int end, int n, const AdjList& adj) {
        const vector<long long> dist = ::dijkstra(n, adj, start);
        return dist[end] == INF ? -1 : static_cast<int>(dist[end]);
    }
};

// ============================================================================
// 12. 自验证
// ============================================================================
// 每一组都拿「另一条完全独立的实现」当标准答案：
//   Dijkstra / Bellman-Ford 对拍 Floyd；Kruskal 对拍 Prim 与 Prüfer 全枚举；
//   匈牙利对拍最大流；最大流对拍暴力枚举割；LCA 对拍暴力爬树；
//   2-SAT 对拍 2^n 赋值枚举；差分约束对拍整数解枚举。
// 随机图都从固定种子出发，因此失败可复现。

namespace {

int g_failed = 0;        // 当前这一组的失败数
int g_total_failed = 0;  // 全局累计

void expect(bool cond, const string& what) {
    if (cond) return;
    ++g_failed;
    if (g_failed <= 5) cout << "    [FAIL] " << what << endl;  // 只印前几条，避免刷屏
}

void begin_check() { g_failed = 0; }

void end_check(const string& name, int cases) {
    g_total_failed += g_failed;
    cout << (g_failed == 0 ? "[OK]   " : "[FAIL] ") << name << "  (" << cases << " 组)";
    if (g_failed != 0) cout << "  失败 " << g_failed << " 处";
    cout << endl;
}

// 随机有向图（无自环、无重边）
AdjList random_directed(int n, int m) {
    AdjList adj(n);
    set<pair<int, int>> seen;
    for (int guard = 0; static_cast<int>(seen.size()) < m && guard < m * 20 + 50; ++guard) {
        const int u = rnd(n);
        const int v = rnd(n);
        if (u == v || !seen.insert({u, v}).second) continue;
        adj[u].push_back({v, 1});
    }
    return adj;
}

// 随机无向边表（无自环、无重边）
vector<Edge> random_undirected(int n, int m, int max_w) {
    vector<Edge> edges;
    set<pair<int, int>> seen;
    for (int guard = 0; static_cast<int>(edges.size()) < m && guard < m * 20 + 50; ++guard) {
        int u = rnd(n);
        int v = rnd(n);
        if (u == v) continue;
        if (u > v) std::swap(u, v);
        if (!seen.insert({u, v}).second) continue;
        edges.push_back({u, v, 1 + rnd(max_w)});
    }
    return edges;
}

// 随机树（无向）
vector<vector<int>> random_tree(int n) {
    vector<vector<int>> tree(n);
    for (int v = 1; v < n; ++v) {
        const int p = rnd(v);
        tree[p].push_back(v);
        tree[v].push_back(p);
    }
    return tree;
}

// 传递闭包：reach[u][v] = 1 表示 u 能到 v。用来当 SCC 的标准答案
vector<vector<char>> reachability(int n, const AdjList& adj) {
    vector<vector<char>> reach(n, vector<char>(n, 0));
    for (int u = 0; u < n; ++u) {
        for (const auto& e : adj[u]) reach[u][e.first] = 1;
    }
    for (int k = 0; k < n; ++k) {
        for (int i = 0; i < n; ++i) {
            if (!reach[i][k]) continue;
            for (int j = 0; j < n; ++j) {
                if (reach[k][j]) reach[i][j] = 1;
            }
        }
    }
    return reach;
}

// Prüfer 序列 -> 生成树的边集（用来枚举所有生成树当 MST 的标准答案）
vector<pair<int, int>> prufer_to_tree(const vector<int>& seq, int n) {
    vector<int> degree(n, 1);
    for (int x : seq) ++degree[x];
    vector<pair<int, int>> es;
    for (int x : seq) {
        for (int leaf = 0; leaf < n; ++leaf) {
            if (degree[leaf] != 1) continue;
            es.push_back({leaf, x});
            --degree[leaf];
            --degree[x];
            break;
        }
    }
    vector<int> rest;
    for (int i = 0; i < n; ++i) {
        if (degree[i] == 1) rest.push_back(i);
    }
    if (rest.size() == 2) es.push_back({rest[0], rest[1]});
    return es;
}

// 暴力 MST：枚举所有 n^(n-2) 棵生成树，取最小权值
long long brute_mst(int n, const vector<Edge>& edges) {
    vector<vector<long long>> w(n, vector<long long>(n, INF));
    for (const auto& e : edges) {
        w[e.u][e.v] = min(w[e.u][e.v], static_cast<long long>(e.w));
        w[e.v][e.u] = w[e.u][e.v];
    }
    if (n == 1) return 0;
    if (n == 2) return w[0][1] == INF ? -1 : w[0][1];

    int total = 1;
    for (int i = 0; i < n - 2; ++i) total *= n;

    long long best = INF;
    vector<int> seq(n - 2, 0);
    for (int code = 0; code < total; ++code) {
        int rest = code;
        for (int i = 0; i < n - 2; ++i) {
            seq[i] = rest % n;
            rest /= n;
        }
        long long sum = 0;
        bool ok = true;
        for (const auto& e : prufer_to_tree(seq, n)) {
            if (w[e.first][e.second] == INF) {
                ok = false;
                break;
            }
            sum += w[e.first][e.second];
        }
        if (ok) best = min(best, sum);
    }
    return best == INF ? -1 : best;
}

}  // namespace

int main() {
    cout << "===== algo_graph 自验证（每组都是「实现对拍另一条独立路径」）=====" << endl;

    // ---------- 1. 遍历 ----------
    begin_check();
    {
        // 手画的小树：0-1, 0-2, 1-3, 1-4, 2-5
        AdjList adj(6);
        auto link = [&](int a, int b) {
            adj[a].push_back({b, 1});
            adj[b].push_back({a, 1});
        };
        link(0, 1);
        link(0, 2);
        link(1, 3);
        link(1, 4);
        link(2, 5);

        const vector<int> bfs = bfs_order(6, adj, 0);
        expect(bfs.size() == 6, "BFS 应访问全部 6 个点");
        expect(bfs.front() == 0 && bfs.back() == 5, "BFS 按层：0 最先、第 2 层的 5 最后");

        const vector<long long> dist = bfs_sssp(6, adj, 0);
        expect(dist[0] == 0 && dist[3] == 2 && dist[5] == 2, "无权最短路：d(0)=0、d(3)=2、d(5)=2");

        const vector<int> dfs = dfs_order(6, adj, 0);
        expect(dfs == (vector<int>{0, 1, 3, 4, 2, 5}), "DFS 前序应为 0 1 3 4 2 5（与递归版一致）");

        AdjList two(4);  // 一条边 + 两个孤立点
        two[0].push_back({1, 1});
        two[1].push_back({0, 1});
        expect(count_components(4, two) == 3, "一条边 + 两个孤立点 -> 3 个连通块");
    }
    end_check("1. 遍历：BFS 层序 / DFS 前序 / 无权最短路 / 连通块", 5);

    // ---------- 2. 拓扑 ----------
    begin_check();
    {
        // 经典 DAG：5→2, 5→0, 4→0, 4→1, 2→3, 3→1
        AdjList dag(6);
        auto add = [&](int a, int b) { dag[a].push_back({b, 1}); };
        add(5, 2);
        add(5, 0);
        add(4, 0);
        add(4, 1);
        add(2, 3);
        add(3, 1);

        const vector<int> order = topo_kahn(6, dag);
        expect(order.size() == 6, "DAG 应得到含 6 个点的拓扑序");
        expect(!has_cycle_dfs(6, dag), "DAG 不应被判有环");

        vector<int> pos(6, -1);
        for (int i = 0; i < static_cast<int>(order.size()); ++i) pos[order[i]] = i;
        bool ordered = true;
        for (int u = 0; u < 6; ++u) {
            for (const auto& e : dag[u]) {
                if (pos[u] > pos[e.first]) ordered = false;
            }
        }
        expect(ordered, "拓扑序必须满足每条边 u→v 都有 pos[u] < pos[v]");

        AdjList cycle(3);
        cycle[0].push_back({1, 1});
        cycle[1].push_back({2, 1});
        cycle[2].push_back({0, 1});
        expect(topo_kahn(3, cycle).empty(), "有环时 Kahn 必须返回空");
        expect(has_cycle_dfs(3, cycle), "有环时三色必须判 true");

        // 随机图：两种判环方式必须完全一致
        const int rounds = 800;
        for (int round = 0; round < rounds; ++round) {
            const int n = 1 + rnd(7);
            const AdjList g = random_directed(n, rnd(12));
            expect(topo_kahn(n, g).empty() == has_cycle_dfs(n, g),
                   "Kahn 与三色的判环结论不一致");
        }
        end_check("2. 拓扑：Kahn 对拍 DFS 三色", 6 + rounds);
    }

    // ---------- 3. 强连通分量 ----------
    begin_check();
    {
        const int rounds = 400;
        for (int round = 0; round < rounds; ++round) {
            const int n = 1 + rnd(7);
            const AdjList g = random_directed(n, rnd(12));
            int comps = 0;
            const vector<int> comp = tarjan_scc(n, g, comps);
            const vector<vector<char>> reach = reachability(n, g);

            // (a) 同一分量 ⟺ 互相可达
            for (int u = 0; u < n; ++u) {
                for (int v = 0; v < n; ++v) {
                    const bool mutual = (u == v) || (reach[u][v] && reach[v][u]);
                    expect(mutual == (comp[u] == comp[v]), "SCC 等价类与「互相可达」不一致");
                }
            }
            // (b) 跨分量的边只能从编号大指向编号小（Tarjan 编号是逆拓扑序）
            for (int u = 0; u < n; ++u) {
                for (const auto& e : g[u]) {
                    if (comp[u] != comp[e.first]) expect(comp[u] > comp[e.first], "分量编号不是逆拓扑序");
                }
            }
        }
        end_check("3. SCC：Tarjan 对拍传递闭包 + 缩点后是 DAG", rounds);
    }

    // ---------- 4. 割点 / 桥 ----------
    begin_check();
    {
        const int rounds = 300;
        for (int round = 0; round < rounds; ++round) {
            const int n = 2 + rnd(6);
            const vector<Edge> edges = random_undirected(n, rnd(10), 5);
            const CutInfo info = find_cuts(n, edges);

            // 暴力割点：去掉 v，看 v 的邻居落在几个连通块里（>= 2 就是割点）
            auto is_cut_brute = [&](int skip) {
                vector<int> neighbor;
                for (const auto& e : edges) {
                    if (e.u == skip) neighbor.push_back(e.v);
                    if (e.v == skip) neighbor.push_back(e.u);
                }
                if (neighbor.empty()) return false;
                UnionFind uf(n);
                for (const auto& e : edges) {
                    if (e.u == skip || e.v == skip) continue;
                    uf.unite(e.u, e.v);
                }
                set<int> roots;
                for (int v : neighbor) roots.insert(uf.find(v));
                return roots.size() >= 2;
            };

            for (int v = 0; v < n; ++v) {
                expect((info.is_cut[v] != 0) == is_cut_brute(v), "割点判定与暴力不一致");
            }

            // 暴力桥：去掉这条边，两端是否断开
            for (int i = 0; i < static_cast<int>(edges.size()); ++i) {
                UnionFind uf(n);
                for (int j = 0; j < static_cast<int>(edges.size()); ++j) {
                    if (j == i) continue;
                    uf.unite(edges[j].u, edges[j].v);
                }
                const bool brute = !uf.connected(edges[i].u, edges[i].v);
                const pair<int, int> key{min(edges[i].u, edges[i].v), max(edges[i].u, edges[i].v)};
                const bool found = find(info.bridges.begin(), info.bridges.end(), key) !=
                                   info.bridges.end();
                expect(found == brute, "桥判定与暴力不一致");
            }
        }
        end_check("4. 割点 / 桥：Tarjan 对拍「删点 / 删边后看连通性」", rounds);
    }

    // ---------- 5. 最短路 ----------
    begin_check();
    {
        int cases = 0;

        // (a) 非负权：Dijkstra / Bellman-Ford / Floyd 三者全源全对
        for (int round = 0; round < 150; ++round) {
            const int n = 2 + rnd(6);
            AdjList adj(n);
            vector<Edge> edges;
            vector<vector<long long>> mat(n, vector<long long>(n, INF));
            set<pair<int, int>> seen;
            for (int i = 0; i < n; ++i) mat[i][i] = 0;
            const int m = rnd(14);
            for (int k = 0; k < m; ++k) {
                const int u = rnd(n);
                const int v = rnd(n);
                if (u == v || !seen.insert({u, v}).second) continue;
                const int w = rnd(10);
                edges.push_back({u, v, w});
                adj[u].push_back({v, w});
                mat[u][v] = w;
            }

            const vector<vector<long long>> fw = floyd(n, mat);
            for (int s = 0; s < n; ++s) {
                const vector<long long> dj = dijkstra(n, adj, s);
                const ShortestResult bf = bellman_ford(n, edges, s);
                expect(!bf.has_negative_cycle, "非负权不该出现负环");
                for (int v = 0; v < n; ++v) {
                    expect(dj[v] == fw[s][v], "Dijkstra 与 Floyd 不一致");
                    expect(bf.dist[v] == fw[s][v], "Bellman-Ford 与 Floyd 不一致");
                }
            }
            ++cases;
        }

        // (b) 负权（但无负环）：边只从小编号指向大编号，DAG 不可能有环
        for (int round = 0; round < 150; ++round) {
            const int n = 2 + rnd(6);
            vector<Edge> edges;
            vector<vector<long long>> mat(n, vector<long long>(n, INF));
            for (int i = 0; i < n; ++i) mat[i][i] = 0;
            for (int k = 0, m = rnd(10); k < m; ++k) {
                const int u = rnd(n - 1);                        // 0 .. n-2
                const int v = u + 1 + rnd(n - u - 1);            // u+1 .. n-1
                const int w = rnd(11) - 5;                       // -5 .. 5
                if (mat[u][v] != INF) continue;                  // 不弄重边
                edges.push_back({u, v, w});
                mat[u][v] = w;
            }

            const vector<vector<long long>> fw = floyd(n, mat);
            for (int s = 0; s < n; ++s) {
                const ShortestResult bf = bellman_ford(n, edges, s);
                expect(!bf.has_negative_cycle, "DAG 上不该出现负环");
                for (int v = 0; v < n; ++v) {
                    expect(bf.dist[v] == fw[s][v], "负权下 Bellman-Ford 与 Floyd 不一致");
                }
            }
            ++cases;
        }

        // (c) 负环：0→1(1) → 2(-1) → 0(-1)，一圈下来 -1
        {
            const vector<Edge> edges = {{0, 1, 1}, {1, 2, -1}, {2, 0, -1}};
            expect(bellman_ford(3, edges, 0).has_negative_cycle, "Bellman-Ford 应检出负环");

            vector<vector<long long>> mat(3, vector<long long>(3, INF));
            for (int i = 0; i < 3; ++i) mat[i][i] = 0;
            for (const auto& e : edges) mat[e.u][e.v] = e.w;
            const vector<vector<long long>> fw = floyd(3, mat);
            bool negative = false;
            for (int i = 0; i < 3; ++i) {
                if (fw[i][i] < 0) negative = true;
            }
            expect(negative, "Floyd 侧也应看到 dist[i][i] < 0");
            ++cases;
        }

        // (d) 0-1 BFS == Dijkstra（边权只取 0/1）
        for (int round = 0; round < 150; ++round) {
            const int n = 2 + rnd(6);
            AdjList adj(n);
            set<pair<int, int>> seen;
            const int m = rnd(14);
            for (int k = 0; k < m; ++k) {
                const int u = rnd(n);
                const int v = rnd(n);
                if (u == v || !seen.insert({u, v}).second) continue;
                adj[u].push_back({v, rnd(2)});
            }
            for (int s = 0; s < n; ++s) {
                expect(zero_one_bfs(n, adj, s) == dijkstra(n, adj, s), "0-1 BFS 与 Dijkstra 不一致");
            }
            ++cases;
        }

        // (e) A*：h = 0 退化成 Dijkstra；h 取真实剩余距离也必须给同一答案
        {
            AdjList adj(4);
            auto add = [&](int a, int b, int w) { adj[a].push_back({b, w}); };
            add(0, 1, 1);
            add(0, 2, 4);
            add(1, 2, 2);
            add(1, 3, 6);
            add(2, 3, 3);
            const int target = 3;
            const vector<long long> truth = dijkstra(4, adj, 0);
            expect(truth[target] == 6, "d(0→3) 应为 6（0-1-2-3）");

            const vector<long long> h_zero(4, 0);
            expect(astar(4, adj, 0, target, h_zero)[target] == truth[target],
                   "A* 的 h 全 0 时应等价于 Dijkstra");

            vector<long long> h_exact(4, 0);
            for (int v = 0; v < 4; ++v) h_exact[v] = truth[v] == INF ? 0 : truth[v];
            expect(astar(4, adj, 0, target, h_exact)[target] == truth[target],
                   "A* 用真实距离当启发式也必须得到同一答案");
            ++cases;
        }

        end_check("5. 最短路：Dijkstra / Bellman-Ford 对拍 Floyd，0-1 BFS、A* 对拍 Dijkstra", cases);
    }

    // ---------- 6. 最小生成树 ----------
    begin_check();
    {
        int cases = 0;

        // (a) Kruskal 对拍 Prim
        for (int round = 0; round < 250; ++round) {
            const int n = 2 + rnd(6);
            const vector<Edge> edges = random_undirected(n, n - 1 + rnd(6), 9);
            vector<Edge> a;
            vector<Edge> b;
            const long long by_kruskal = kruskal(n, edges, &a);
            const long long by_prim = prim(n, edges, &b);
            expect(by_kruskal == by_prim, "Kruskal 与 Prim 的 MST 总权值不一致");
            if (by_kruskal >= 0) {
                expect(static_cast<int>(a.size()) == n - 1, "Kruskal 结果的边数应为 n-1");
                expect(static_cast<int>(b.size()) == n - 1, "Prim 结果的边数应为 n-1");
            }
            ++cases;
        }

        // (b) 对拍 Prüfer 全枚举（n <= 5，最多 125 棵生成树）
        for (int round = 0; round < 80; ++round) {
            const int n = 3 + rnd(3);
            const vector<Edge> edges = random_undirected(n, n - 1 + rnd(4), 9);
            expect(kruskal(n, edges) == brute_mst(n, edges), "Kruskal 与全枚举生成树的最优值不一致");
            ++cases;
        }

        // (c) 不连通图应返回 -1
        {
            const vector<Edge> edges = {{0, 1, 5}};  // 点 2 是孤岛
            expect(kruskal(3, edges) == -1, "不连通图没有生成树，应返回 -1");
            expect(prim(3, edges) == -1, "Prim 也应对不连通图返回 -1");
            ++cases;
        }

        end_check("6. MST：Kruskal 对拍 Prim 与 Prüfer 全枚举", cases);
    }

    // ---------- 7. 二分图 + 匹配 ----------
    begin_check();
    {
        int cases = 0;

        // (a) 染色对拍「枚举所有 2^n 种着色」
        for (int round = 0; round < 250; ++round) {
            const int n = 2 + rnd(7);
            const vector<Edge> edges = random_undirected(n, rnd(12), 1);
            AdjList adj(n);
            for (const auto& e : edges) {
                adj[e.u].push_back({e.v, 1});
                adj[e.v].push_back({e.u, 1});
            }

            bool brute = false;
            for (int mask = 0; mask < (1 << n) && !brute; ++mask) {
                bool ok = true;
                for (const auto& e : edges) {
                    if (((mask >> e.u) & 1) == ((mask >> e.v) & 1)) {
                        ok = false;
                        break;
                    }
                }
                if (ok) brute = true;
            }
            expect(is_bipartite(n, adj) == brute, "二分图判定与暴力着色不一致");
            ++cases;
        }

        // (b) 匈牙利对拍最大流（网络：S→左侧→右侧→T，容量全 1）
        for (int round = 0; round < 150; ++round) {
            const int n_left = 1 + rnd(5);
            const int n_right = 1 + rnd(5);
            const int sink = n_left + n_right;
            const int source = sink + 1;

            vector<vector<int>> left_adj(n_left);
            Dinic dinic(source + 1);
            for (int i = 0; i < n_left; ++i) dinic.add_edge(source, i, 1);
            for (int j = 0; j < n_right; ++j) dinic.add_edge(n_left + j, sink, 1);
            for (int i = 0; i < n_left; ++i) {
                for (int j = 0; j < n_right; ++j) {
                    if (rnd(2) == 0) continue;
                    left_adj[i].push_back(j);
                    dinic.add_edge(i, n_left + j, 1);
                }
            }

            const long long by_flow = dinic.max_flow(source, sink);
            expect(hungarian(n_left, n_right, left_adj) == static_cast<int>(by_flow),
                   "匈牙利与最大流算出的匹配数不一致");
            ++cases;
        }

        end_check("7. 二分图：染色对拍枚举，匈牙利对拍最大流", cases);
    }

    // ---------- 8. 最大流 / 最小割 ----------
    begin_check();
    {
        const int rounds = 250;
        for (int round = 0; round < rounds; ++round) {
            const int n = 3 + rnd(5);  // 3..7
            const int source = 0;
            const int sink = n - 1;

            vector<Edge> caps;  // w 在这里当容量用
            Dinic dinic(n);
            set<pair<int, int>> seen;
            const int m = rnd(10);
            for (int k = 0; k < m; ++k) {
                const int u = rnd(n);
                const int v = rnd(n);
                if (u == v || !seen.insert({u, v}).second) continue;
                const int c = 1 + rnd(5);
                caps.push_back({u, v, c});
                dinic.add_edge(u, v, c);
            }

            const long long flow = dinic.max_flow(source, sink);

            // 暴力最小割：枚举所有「包含 s、不含 t」的点集
            long long best = INF;
            for (int mask = 0; mask < (1 << n); ++mask) {
                if (((mask >> source) & 1) == 0 || ((mask >> sink) & 1) != 0) continue;
                long long capacity = 0;
                for (const auto& e : caps) {
                    if (((mask >> e.u) & 1) != 0 && ((mask >> e.v) & 1) == 0) capacity += e.w;
                }
                best = min(best, capacity);
            }
            expect(flow == best, "最大流不等于暴力枚举的最小割");

            // 由残量网络反推出的 S 侧，其割容量也必须等于最大流
            const vector<char> side = dinic.min_cut(source);
            long long cut = 0;
            for (const auto& e : caps) {
                if (side[e.u] != 0 && side[e.v] == 0) cut += e.w;
            }
            expect(cut == flow, "min_cut 给出的 S 侧割容量应等于最大流");
        }
        end_check("8. 最大流：Dinic 对拍暴力枚举最小割", rounds);
    }

    // ---------- 9. LCA 与树的直径 ----------
    begin_check();
    {
        const int rounds = 100;
        for (int round = 0; round < rounds; ++round) {
            const int n = 2 + rnd(14);
            const vector<vector<int>> tree = random_tree(n);
            const Lca lca(n, tree, 0);

            // 暴力：标出 u 的所有祖先，沿 v 往上爬，第一个被标记的就是 LCA
            vector<int> parent(n, -1);
            vector<int> depth(n, 0);
            vector<int> q{0};
            parent[0] = 0;
            for (size_t head = 0; head < q.size(); ++head) {
                for (int v : tree[q[head]]) {
                    if (parent[v] != -1) continue;
                    parent[v] = q[head];
                    depth[v] = depth[q[head]] + 1;
                    q.push_back(v);
                }
            }

            int max_dist = 0;
            for (int u = 0; u < n; ++u) {
                vector<char> mark(n, 0);
                for (int x = u;; x = parent[x]) {
                    mark[x] = 1;
                    if (x == 0) break;
                }
                for (int v = 0; v < n; ++v) {
                    int y = v;
                    while (!mark[y]) y = parent[y];
                    expect(lca.query(u, v) == y, "LCA 与暴力爬树不一致");
                    const int d = depth[u] + depth[v] - 2 * depth[y];
                    expect(lca.distance(u, v) == d, "树上距离公式不一致");
                    max_dist = max(max_dist, d);
                }
            }

            int end_a = 0;
            int end_b = 0;
            expect(tree_diameter(n, tree, &end_a, &end_b) == max_dist,
                   "两次 BFS 求出的直径应等于所有点对距离的最大值");
        }
        end_check("9. LCA / 直径：倍增对拍暴力爬树", rounds);
    }

    // ---------- 10. 欧拉路 ----------
    begin_check();
    {
        int cases = 0;

        // 三角形：全偶度 -> 欧拉回路
        {
            const vector<Edge> edges = {{0, 1, 1}, {1, 2, 1}, {2, 0, 1}};
            bool ok = false;
            const vector<int> path = hierholzer(3, edges, 0, &ok);
            expect(ok && path.size() == 4, "三角形应有欧拉回路，长度 3+1");
            ++cases;
        }

        // 两条边连成链：两个奇度点 -> 必须从奇度点出发
        {
            const vector<Edge> edges = {{0, 1, 1}, {1, 2, 1}};
            bool ok = false;
            const vector<int> path = hierholzer(3, edges, 0, &ok);
            expect(ok && path == (vector<int>{0, 1, 2}), "链 0-1-2 的欧拉路应为 0 1 2");
            ++cases;
        }

        // 随机图：长度正确 + 相邻两点之间确实有一条未使用的边 + 所有边都被用上
        for (int round = 0; round < 250; ++round) {
            const int n = 2 + rnd(6);
            const vector<Edge> edges = random_undirected(n, rnd(9), 1);
            if (edges.empty()) continue;

            vector<int> degree(n, 0);
            for (const auto& e : edges) {
                ++degree[e.u];
                ++degree[e.v];
            }
            int odd_count = 0;
            int odd_vertex = -1;
            for (int v = 0; v < n; ++v) {
                if (degree[v] % 2 == 0) continue;
                ++odd_count;
                odd_vertex = v;
            }
            if (odd_count != 0 && odd_count != 2) continue;  // 度数条件不满足，本题无解

            const int start = (odd_count == 2) ? odd_vertex : edges[0].u;
            bool ok = false;
            const vector<int> path = hierholzer(n, edges, start, &ok);
            if (!ok) continue;  // 不连通：有边走不到，属正常

            expect(path.size() == edges.size() + 1, "欧拉路长度应为 边数 + 1");

            vector<char> used_edge(edges.size(), 0);
            bool valid = true;
            for (size_t i = 0; i + 1 < path.size(); ++i) {
                const int a = path[i];
                const int b = path[i + 1];
                int found = -1;
                for (int k = 0; k < static_cast<int>(edges.size()); ++k) {
                    if (used_edge[k]) continue;
                    const bool match = (edges[k].u == a && edges[k].v == b) ||
                                       (edges[k].u == b && edges[k].v == a);
                    if (match) {
                        found = k;
                        break;
                    }
                }
                if (found == -1) {
                    valid = false;
                    break;
                }
                used_edge[found] = 1;
            }
            expect(valid, "欧拉路的相邻两点之间必须存在一条尚未使用的边");
            expect(all_of(used_edge.begin(), used_edge.end(), [](char c) { return c != 0; }),
                   "欧拉路必须恰好用上所有边");
            ++cases;
        }

        end_check("10. 欧拉路：Hierholzer + 路径合法性校验", cases);
    }

    // ---------- 11. 差分约束 ----------
    begin_check();
    {
        const int rounds = 150;
        for (int round = 0; round < rounds; ++round) {
            const int n = 1 + rnd(3);  // 1..3，便于暴力枚举
            vector<DiffConstraint> cons;
            for (int k = 0, m = rnd(4); k < m; ++k) {
                cons.push_back({rnd(n), rnd(n), rnd(5) - 2});
            }

            // 暴力：枚举 x_i ∈ [-6, 6]。有解时总可以整体平移，且相邻两个值之差不超过 |c|，
            // 所以 n <= 3、|c| <= 2 时这个区间一定够用。
            vector<int> x(n, 0);
            bool brute = false;
            {
                function<bool(int)> go = [&](int k) {
                    if (k == n) {
                        for (const auto& c : cons) {
                            if (x[c.j] - x[c.i] > c.c) return false;
                        }
                        return true;
                    }
                    for (int v = -6; v <= 6; ++v) {
                        x[k] = v;
                        if (go(k + 1)) return true;
                    }
                    return false;
                };
                brute = go(0);
            }

            const DiffResult res = diff_constraints(n, cons);
            expect(res.feasible == brute, "差分约束的可满足性与暴力枚举不一致");
            if (res.feasible) {
                for (const auto& c : cons) {
                    expect(res.x[c.j] - res.x[c.i] <= c.c, "差分约束给出的解必须满足所有不等式");
                }
            }
        }
        end_check("11. 差分约束：Bellman-Ford 判负环 对拍 整数解枚举", rounds);
    }

    // ---------- 12. 2-SAT ----------
    begin_check();
    {
        const int rounds = 250;
        for (int round = 0; round < rounds; ++round) {
            const int n_vars = 1 + rnd(4);
            vector<TwoSatClause> clauses;
            for (int k = 0, m = rnd(5); k < m; ++k) {
                clauses.push_back({rnd(n_vars), rnd(2) == 1, rnd(n_vars), rnd(2) == 1});
            }

            bool brute = false;
            for (int mask = 0; mask < (1 << n_vars) && !brute; ++mask) {
                bool ok = true;
                for (const auto& c : clauses) {
                    const bool a = ((mask >> c.a) & 1) != 0;
                    const bool b = ((mask >> c.b) & 1) != 0;
                    if (a != c.va && b != c.vb) {
                        ok = false;
                        break;
                    }
                }
                if (ok) brute = true;
            }

            vector<char> assignment;
            const bool sat = two_sat(n_vars, clauses, &assignment);
            expect(sat == brute, "2-SAT 的可满足性与 2^n 枚举不一致");
            if (!sat) continue;
            for (const auto& c : clauses) {
                const bool a = assignment[c.a] != 0;
                const bool b = assignment[c.b] != 0;
                expect(a == c.va || b == c.vb, "2-SAT 给出的赋值必须满足所有子句");
            }
        }
        end_check("12. 2-SAT：Tarjan SCC 对拍 2^n 赋值枚举", rounds);
    }

    // ---------- 13. 旧接口兼容 ----------
    begin_check();
    {
        AdjList adj(4);
        auto add = [&](int a, int b, int w) { adj[a].push_back({b, w}); };
        add(0, 1, 1);
        add(0, 2, 2);
        add(1, 3, 5);
        add(2, 3, 1);

        AlgoGraph old_api;
        expect(old_api.BreadthFirstSearch(0, adj) == bfs_order(4, adj, 0), "AlgoGraph::BFS 应等价于 bfs_order");
        expect(old_api.DepthFirstSearch(0, adj) == dfs_order(4, adj, 0), "AlgoGraph::DFS 应等价于 dfs_order");
        expect(old_api.TopologicalSort(4, adj) == topo_kahn(4, adj), "AlgoGraph::TopologicalSort 应等价于 topo_kahn");
        expect(old_api.dijkstra(0, 3, 4, adj) == 3, "AlgoGraph::dijkstra(0→3) 应为 3（0-2-3）");
    }
    end_check("13. 旧接口 AlgoGraph 与新实现一致", 4);

    cout << endl;
    if (g_total_failed == 0) {
        cout << "algo_graph: all checks passed" << endl;
        return 0;
    }
    cout << "algo_graph: FAILED, 共 " << g_total_failed << " 处不一致" << endl;
    return 1;
}
