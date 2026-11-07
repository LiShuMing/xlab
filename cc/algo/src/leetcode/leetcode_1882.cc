#include <random>

#include "../include/fwd.h"
/**
给你两个 下标从 0 开始 的整数数组 servers 和 tasks ，长度分别为 n​​​​​​ 和 m​​​​​​ 。servers[i] 是第 i​​​​​​​​​​ 台服务器的 权重 ，而 tasks[j] 是处理第 j​​​​​​ 项任务 所需要的时间（单位：秒）。

你正在运行一个仿真系统，在处理完所有任务后，该系统将会关闭。每台服务器只能同时处理一项任务。第 0 项任务在第 0 秒可以开始处理，相应地，第 j 项任务在第 j 秒可以开始处理。处理第 j 项任务时，你需要为它分配一台 权重最小 的空闲服务器。如果存在多台相同权重的空闲服务器，请选择 下标最小 的服务器。
如果一台空闲服务器在第 t 秒分配到第 j 项任务，那么在 t + tasks[j] 时它将恢复空闲状态。

如果没有空闲服务器，则必须等待，直到出现一台空闲服务器，并 尽可能早 地处理剩余任务。 如果有多项任务等待分配，则按照 下标递增 的顺序完成分配。

如果同一时刻存在多台空闲服务器，可以同时将多项任务分别分配给它们。

构建长度为 m 的答案数组 ans ，其中 ans[j] 是第 j 项任务分配的服务器的下标。

返回答案数组 ans​​​​ 。
*/
class Solution {
public:
    vector<int> assignTasks(vector<int>& servers, vector<int>& tasks) {
        int n = servers.size();
        int m = tasks.size();
        // free queue: min-heap: <weight, id>
        priority_queue<pair<int, int>, vector<pair<int, int>>, greater<pair<int, int>>> pq;
        for (int i = 0; i < n; i++) {
            pq.push({servers[i], i});
        }
        // busy queue: min-heap, tuple<finish_time, weight, id>
        priority_queue<tuple<long long, int, int>, vector<tuple<long long, int, int>>,
                       greater<tuple<long long, int, int>>>
            busy;

        vector<int> res(m);
        long long now = 0;

        for (int i = 0; i < m; i++) {
            now = max(now, (long long)i);
            // move tasks from busy to free
            // get<0>(busy.top()): finish_time
            // get<1>(busy.top()): weight
            // get<2>(busy.top()): id
            while (!busy.empty() && get<0>(busy.top()) <= now) {
                pq.push({get<1>(busy.top()), get<2>(busy.top())});
                busy.pop();
            }
            if (pq.empty()) {
                now = get<0>(busy.top());
                while (!busy.empty() && get<0>(busy.top()) <= now) {
                    pq.push({get<1>(busy.top()), get<2>(busy.top())});
                    busy.pop();
                }
            }
            res[i] = pq.top().second;
            pq.pop();
            busy.push({now + tasks[i], servers[res[i]], res[i]});
        }
        return res;
    }
};

// 独立参照实现：逐秒模拟，不用任何堆，直接照题面规则推进
static vector<int> bruteForce(const vector<int>& servers, const vector<int>& tasks) {
    int n = servers.size();
    int m = tasks.size();
    vector<long long> freeAt(n, 0);
    vector<bool> done(m, false);
    vector<int> ans(m, -1);
    int assigned = 0;
    long long t = 0;
    while (assigned < m) {
        while (true) {
            int j = -1;
            for (int k = 0; k < m; k++) {
                if (!done[k] && k <= t) {
                    j = k;
                    break;
                }
            }
            if (j < 0) break;
            int best = -1;
            for (int i = 0; i < n; i++) {
                if (freeAt[i] > t) continue;
                if (best < 0 || servers[i] < servers[best] ||
                    (servers[i] == servers[best] && i < best)) {
                    best = i;
                }
            }
            if (best < 0) break;
            done[j] = true;
            ans[j] = best;
            freeAt[best] = t + tasks[j];
            assigned++;
        }
        t++;
    }
    return ans;
}

int main() {
    Solution sol;
    int fail = 0;
    auto check = [&](vector<int> servers, vector<int> tasks, const vector<int>& want) {
        vector<int> got = sol.assignTasks(servers, tasks);
        if (got != want) {
            fail++;
            cout << "FAIL servers=" << strJoin(servers, ",") << " tasks=" << strJoin(tasks, ",")
                 << " want=" << strJoin(want, ",") << " got=" << strJoin(got, ",") << endl;
        }
    };

    check({3, 3, 3}, {1, 2, 3, 4, 5}, {0, 0, 1, 0, 2});
    check({5, 1, 4, 3, 2}, {2, 1, 2, 4, 5, 2, 1}, {1, 4, 1, 4, 1, 3, 2});
    check({10, 20, 30}, {1, 1, 1}, {0, 0, 0});
    check({7}, {3, 1, 1, 1}, {0, 0, 0, 0});      // 单服务器：必须等待
    check({1, 1, 1, 1}, {5, 5, 5}, {0, 1, 2});   // 同权重按下标决胜

    // 随机对拍：双堆实现 vs 逐秒模拟
    mt19937 rng(20261106);
    for (int r = 0; r < 2000 && fail == 0; r++) {
        int n = 1 + (int)(rng() % 6);
        int m = 1 + (int)(rng() % 10);
        vector<int> servers(n), tasks(m);
        for (int& x : servers) x = 1 + (int)(rng() % 5);
        for (int& x : tasks) x = 1 + (int)(rng() % 5);
        if (sol.assignTasks(servers, tasks) != bruteForce(servers, tasks)) {
            fail++;
            cout << "FAIL random servers=" << strJoin(servers, ",") << " tasks="
                 << strJoin(tasks, ",") << endl;
        }
    }

    cout << (fail == 0 ? "all checks passed" : "checks failed") << endl;
    return fail == 0 ? 0 : 1;
}
