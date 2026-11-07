#include "../include/fwd.h"

#include <random>

/**
 * LeetCode 2406. Divide Intervals Into Minimum Number of Groups
 *
 * 与 253 的唯一区别：区间是闭的 [s, e]，共享端点也算冲突。
 * [1,2] 与 [2,3] 不能同组，于是出堆条件从 end <= start 变成 end < start，
 * 事件扫描的先后顺序也得反过来：同一时刻先让区间入场，再结算结束。
 */
class Solution {
public:
    // 贪心：按开始时间扫描，小顶堆放各组当前的结束时刻。
    int minGroups(vector<vector<int>>& intervals) {
        sort(intervals.begin(), intervals.end(),
             [](const vector<int>& a, const vector<int>& b) { return a[0] < b[0]; });
        priority_queue<int, vector<int>, greater<int>> ends;
        int groups = 0;
        for (const auto& iv : intervals) {
            if (!ends.empty() && ends.top() < iv[0]) {
                ends.pop();  // 严格小于才能复用，等于表示端点重叠
            } else {
                ++groups;
            }
            ends.push(iv[1]);
        }
        return groups;
    }

    // 扫描线版：闭区间在端点同时有开始与结束，必须先算开始。
    int minGroupsBySweep(const vector<vector<int>>& intervals) {
        vector<pair<int, int>> events;  // (时刻, 类型)，0 = 开始，1 = 结束
        for (const auto& iv : intervals) {
            events.push_back({iv[0], 0});
            events.push_back({iv[1], 1});
        }
        sort(events.begin(), events.end());  // 同一时刻开始事件排在结束事件之前
        int cur = 0, best = 0;
        for (const auto& ev : events) {
            cur += (ev.second == 0) ? 1 : -1;
            best = max(best, cur);
        }
        return best;
    }
};

// 对拍用暴力解：回溯给区间染色，取最少颜色数。n 很小时才可用。
namespace brute {

// 闭区间 [s, e] 是否相交：只要端点不严格分离就算冲突
bool overlap(const vector<vector<int>>& iv, int a, int b) {
    return !(iv[a][1] < iv[b][0] || iv[b][1] < iv[a][0]);
}

void dfs(const vector<vector<int>>& iv, vector<vector<int>>& groups, int idx, int& best) {
    if (idx == static_cast<int>(iv.size())) {
        best = min(best, static_cast<int>(groups.size()));
        return;
    }
    if (static_cast<int>(groups.size()) >= best) return;  // 已不可能更优
    int used = groups.size();
    for (int g = 0; g <= used; ++g) {
        bool opened = (g == used);  // 新开一组，避免同构枚举
        if (opened) groups.emplace_back();
        bool ok = true;
        for (int other : groups[g]) {
            if (overlap(iv, idx, other)) {
                ok = false;
                break;
            }
        }
        if (ok) {
            groups[g].push_back(idx);
            dfs(iv, groups, idx + 1, best);
            groups[g].pop_back();
        }
        if (opened) groups.pop_back();
    }
}

int minGroups(const vector<vector<int>>& iv) {
    int best = static_cast<int>(iv.size());
    vector<vector<int>> groups;
    dfs(iv, groups, 0, best);
    return best;
}

}  // namespace brute

static void printIntervals(const vector<vector<int>>& iv) {
    cout << "[";
    for (size_t i = 0; i < iv.size(); ++i) {
        cout << (i ? ", " : "") << "[" << iv[i][0] << "," << iv[i][1] << "]";
    }
    cout << "]";
}

int main() {
    Solution sol;

    vector<vector<vector<int>>> cases = {
        {{5, 10}, {6, 8}, {1, 5}, {2, 3}, {1, 10}},   // 3：[1,5] 与 [5,10] 在 5 重叠
        {{1, 3}, {5, 6}, {8, 10}, {11, 13}},          // 1
        {{1, 2}, {2, 3}}                              // 2：同样的输入在 253 里答案是 1
    };
    for (const auto& iv : cases) {
        auto copy = iv;
        int cnt = sol.minGroups(copy);
        cout << "区间: ";
        printIntervals(iv);
        cout << " 最少组数 = " << cnt << ", 扫描线 = " << sol.minGroupsBySweep(iv)
             << ", 暴力 = " << brute::minGroups(iv) << endl;
        assert(sol.minGroupsBySweep(iv) == cnt);
        assert(brute::minGroups(iv) == cnt);
    }

    // 半开与闭的对照：端点相接的区间在 253 可复用、在 2406 不可复用。
    vector<vector<int>> touching = {{1, 2}, {2, 3}};
    auto half_open = touching;
    sort(half_open.begin(), half_open.end());
    int half_open_rooms = 0;
    priority_queue<int, vector<int>, greater<int>> ends;
    for (const auto& iv : half_open) {
        if (!ends.empty() && ends.top() <= iv[0]) ends.pop();
        else ++half_open_rooms;
        ends.push(iv[1]);
    }
    cout << "端点相接 [1,2] [2,3]：半开（253 口径）= " << half_open_rooms
         << " 间, 闭（2406 口径）= " << sol.minGroups(touching) << " 组" << endl;
    assert(half_open_rooms == 1);
    assert(sol.minGroups(touching) == 2);

    mt19937 rng(20261102);
    for (int round = 0; round < 2000; ++round) {
        int n = rng() % 7;  // 0..6 个区间
        vector<vector<int>> iv;
        for (int i = 0; i < n; ++i) {
            int s = rng() % 10;
            int e = s + rng() % 5;  // 允许零长度闭区间 [s, s]
            iv.push_back({s, e});
        }
        auto copy = iv;
        int cnt = sol.minGroups(copy);
        int expect = brute::minGroups(iv);
        if (cnt != expect || sol.minGroupsBySweep(iv) != cnt) {
            cout << "MISMATCH round=" << round << " 区间: ";
            printIntervals(iv);
            cout << " greedy=" << cnt << " sweep=" << sol.minGroupsBySweep(iv)
                 << " brute=" << expect << endl;
            return 1;
        }
    }
    cout << "随机对拍 2000 轮通过：贪心 / 扫描线 / 暴力 一致" << endl;
    return 0;
}
