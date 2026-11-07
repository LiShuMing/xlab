#include <random>

#include "../include/fwd.h"
/**
给你一个二维整数数组 tasks，tasks[i] = [enqueueTime_i, processingTime_i] 表示第 i 项任务
在 enqueueTime_i 时刻到达，需要 processingTime_i 的时间执行。单线程 CPU 的调度规则：
1. 只要 CPU 空闲且有已到达的任务，就执行其中 processingTime 最短的那个；
2. 处理时间相同则选下标最小的；
3. 没有可执行任务时 CPU 空转，直到下一个任务到达。
返回 CPU 执行任务的顺序（原始任务下标）。
*/

class Solution {
public:
    vector<int> getOrder(vector<vector<int>>& tasks) {
        int n = tasks.size();
        // 只排下标，既保留原始编号，也不修改调用方的 tasks
        vector<int> idx(n);
        iota(idx.begin(), idx.end(), 0);

        sort(idx.begin(), idx.end(), [&](int a, int b) {
            if (tasks[a][0] != tasks[b][0]) return tasks[a][0] < tasks[b][0];
            return a < b;
        });

        // 候选堆：<processing_time, 原始下标>，按处理时间升序、同长按下标升序
        priority_queue<pair<int, int>, vector<pair<int, int>>, greater<pair<int, int>>> avail;

        vector<int> res;
        res.reserve(n);
        long long now = 0;
        int next = 0;  // idx 中第一个尚未到达的任务
        while ((int)res.size() < n) {
            if (avail.empty()) {
                now = max(now, (long long)tasks[idx[next]][0]);  // 空转：跳到下一个到达时刻
            }
            while (next < n && tasks[idx[next]][0] <= now) {
                avail.push({tasks[idx[next]][1], idx[next]});
                next++;
            }
            auto [proc, id] = avail.top();
            avail.pop();
            res.push_back(id);
            now += proc;
        }
        return res;
    }
};

// 独立参照实现：逐时刻线性扫描，不用任何堆，直接照题面规则走
static vector<int> bruteForce(const vector<vector<int>>& tasks) {
    int n = tasks.size();
    vector<char> done(n, 0);
    vector<int> order;
    order.reserve(n);
    long long t = 0;
    while ((int)order.size() < n) {
        int best = -1;
        for (int i = 0; i < n; i++) {
            if (done[i] || (long long)tasks[i][0] > t) continue;
            if (best < 0 || tasks[i][1] < tasks[best][1] ||
                (tasks[i][1] == tasks[best][1] && i < best)) {
                best = i;
            }
        }
        if (best < 0) {  // 空转：跳到最早到达的未执行任务
            long long jump = -1;
            for (int i = 0; i < n; i++) {
                if (!done[i] && (jump < 0 || tasks[i][0] < jump)) jump = tasks[i][0];
            }
            t = jump;
            continue;
        }
        done[best] = 1;
        order.push_back(best);
        t += tasks[best][1];
    }
    return order;
}

int main() {
    Solution sol;
    int fail = 0;
    // anchor 非空时额外对照题面样例；期望值仍由 bruteForce 独立算出
    auto verify = [&](const char* name, vector<vector<int>> tasks, const vector<int>& anchor) {
        vector<vector<int>> snapshot = tasks;
        vector<int> got = sol.getOrder(tasks);
        vector<int> want = bruteForce(tasks);
        bool untouched = (tasks == snapshot);  // 不允许修改调用方的 tasks
        bool ok = untouched && (got == want) && (anchor.empty() || got == anchor);
        if (!ok) fail++;
        cout << (ok ? "PASS " : "FAIL ") << name << " -> " << strJoin(got, ",") << endl;
    };

    verify("sample1", {{1, 2}, {2, 4}, {3, 2}, {4, 1}}, {0, 2, 3, 1});
    verify("sample2", {{7, 10}, {7, 12}, {7, 5}, {7, 4}, {7, 2}}, {4, 3, 2, 0, 1});
    verify("sample3",
           {{19, 13}, {16, 9}, {21, 10}, {32, 25}, {37, 4}, {49, 24}, {2, 15}, {38, 41},
            {37, 6}, {45, 4}, {5, 33}},
           {});
    verify("single", {{5, 7}}, {0});
    verify("idle-gap", {{1, 100}, {200, 1}}, {0, 1});
    verify("tie-by-index", {{0, 3}, {0, 3}, {0, 3}}, {0, 1, 2});

    // 随机对拍：小根堆实现 vs 逐时刻扫描
    mt19937 rng(20261106);
    for (int r = 0; r < 2000 && fail == 0; r++) {
        int n = 1 + (int)(rng() % 7);
        vector<vector<int>> tasks(n, vector<int>(2));
        for (int i = 0; i < n; i++) {
            tasks[i][0] = (int)(rng() % 12);
            tasks[i][1] = 1 + (int)(rng() % 5);
        }
        vector<vector<int>> srvSnapshot = tasks;
        vector<int> got = sol.getOrder(tasks);
        vector<int> want = bruteForce(tasks);
        if (got != want || tasks != srvSnapshot) {
            fail++;
            cout << "FAIL random n=" << n << " want=" << strJoin(want, ",") << " got="
                 << strJoin(got, ",") << endl;
        }
    }

    cout << (fail == 0 ? "all checks passed" : "checks failed") << endl;
    return fail == 0 ? 0 : 1;
}
