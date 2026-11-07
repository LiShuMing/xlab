#include "../include/fwd.h"

#include <random>

/**
 * LeetCode 253. Meeting Rooms II
 *
 * 半开区间 [s, e)：前一场在 e 结束、后一场在 e 开始，可以复用同一间会议室。
 * 最少房间数 = 最大重叠数：区间图的着色数等于最大团大小，所以贪心是精确解而非近似。
 */
class Solution {
public:
    // 只要数量：按开始时间扫描，小顶堆里放各房间当前的结束时间。
    int minMeetingRooms(vector<vector<int>>& intervals) {
        sort(intervals.begin(), intervals.end(),
             [](const vector<int>& a, const vector<int>& b) { return a[0] < b[0]; });
        priority_queue<int, vector<int>, greater<int>> ends;
        int rooms = 0;
        for (const auto& iv : intervals) {
            if (!ends.empty() && ends.top() <= iv[0]) {
                ends.pop();  // 堆顶是最早空出来的房间，能衔接就复用
            } else {
                ++rooms;
            }
            ends.push(iv[1]);
        }
        return rooms;
    }

    // 双指针版：只数事件，不给方案，用来验证“最少房间数 = 最大重叠数”。
    int minMeetingRoomsBySweep(const vector<vector<int>>& intervals) {
        vector<int> starts, ends;
        for (const auto& iv : intervals) {
            starts.push_back(iv[0]);
            ends.push_back(iv[1]);
        }
        sort(starts.begin(), starts.end());
        sort(ends.begin(), ends.end());
        int cur = 0, best = 0;
        for (size_t i = 0, j = 0; i < starts.size(); ++i) {
            // 半开区间：同一时刻先结算结束事件，再让新会议入场。
            while (j < ends.size() && ends[j] <= starts[i]) {
                ++j;
                --cur;
            }
            ++cur;
            best = max(best, cur);
        }
        return best;
    }

    // 数量加方案：堆里带房间号，写出每个输入区间所在的房间。
    int assignRooms(const vector<vector<int>>& intervals, vector<int>& room_of) {
        int n = intervals.size();
        room_of.assign(n, -1);
        vector<int> order(n);
        iota(order.begin(), order.end(), 0);
        sort(order.begin(), order.end(), [&](int a, int b) {
            if (intervals[a][0] != intervals[b][0]) return intervals[a][0] < intervals[b][0];
            return intervals[a][1] < intervals[b][1];  // 同起点先排短的，保证输出稳定
        });
        // (空闲时刻, 房间号)
        priority_queue<pair<int, int>, vector<pair<int, int>>, greater<pair<int, int>>> free_at;
        int rooms = 0;
        for (int idx : order) {
            int s = intervals[idx][0], e = intervals[idx][1];
            if (!free_at.empty() && free_at.top().first <= s) {
                room_of[idx] = free_at.top().second;
                free_at.pop();
            } else {
                room_of[idx] = rooms++;
            }
            free_at.push({e, room_of[idx]});
        }
        return rooms;
    }
};

// 对拍用暴力解：回溯给区间染色，取最少颜色数。n 很小时才可用。
namespace brute {

// 半开区间 [s, e) 是否相交
bool overlap(const vector<vector<int>>& iv, int a, int b) {
    return iv[a][0] < iv[b][1] && iv[b][0] < iv[a][1];
}

void dfs(const vector<vector<int>>& iv, vector<vector<int>>& rooms, int idx, int& best) {
    if (idx == static_cast<int>(iv.size())) {
        best = min(best, static_cast<int>(rooms.size()));
        return;
    }
    if (static_cast<int>(rooms.size()) >= best) return;  // 已不可能更优
    int used = rooms.size();
    for (int r = 0; r <= used; ++r) {
        bool opened = (r == used);  // 新开一间，避免同构枚举
        if (opened) rooms.emplace_back();
        bool ok = true;
        for (int other : rooms[r]) {
            if (overlap(iv, idx, other)) {
                ok = false;
                break;
            }
        }
        if (ok) {
            rooms[r].push_back(idx);
            dfs(iv, rooms, idx + 1, best);
            rooms[r].pop_back();
        }
        if (opened) rooms.pop_back();
    }
}

int minRooms(const vector<vector<int>>& iv) {
    int best = static_cast<int>(iv.size());
    vector<vector<int>> rooms;
    dfs(iv, rooms, 0, best);
    return best;
}

}  // namespace brute

static void printIntervals(const vector<vector<int>>& iv) {
    cout << "[";
    for (size_t i = 0; i < iv.size(); ++i) {
        cout << (i ? ", " : "") << "[" << iv[i][0] << "," << iv[i][1] << ")";
    }
    cout << "]";
}

// 校验方案：所有区间都被分到合法房间，且同一房间内两两不相交。
static bool checkAssignment(const vector<vector<int>>& iv, const vector<int>& room_of, int rooms) {
    if (static_cast<int>(room_of.size()) != static_cast<int>(iv.size())) return false;
    int max_room = -1;
    for (int r : room_of) {
        if (r < 0 || r >= rooms) return false;
        max_room = max(max_room, r);
    }
    if (max_room + 1 != rooms) return false;
    for (int i = 0; i < static_cast<int>(iv.size()); ++i) {
        for (int j = i + 1; j < static_cast<int>(iv.size()); ++j) {
            if (room_of[i] == room_of[j] && brute::overlap(iv, i, j)) return false;
        }
    }
    return true;
}

int main() {
    Solution sol;

    vector<vector<vector<int>>> cases = {
        {{0, 30}, {5, 10}, {15, 20}},     // 2：两段各占一间，复用一次
        {{7, 10}, {2, 4}},                // 1
        {{1, 3}, {2, 4}, {3, 5}, {4, 6}}  // 2：[1,3) 与 [3,5) 端点相接，可复用
    };
    for (const auto& iv : cases) {
        auto copy = iv;
        int cnt = sol.minMeetingRooms(copy);
        vector<int> room_of;
        int assigned = sol.assignRooms(iv, room_of);
        cout << "会议: ";
        printIntervals(iv);
        cout << " 最少房间 = " << cnt << ", 分配 = [";
        for (size_t i = 0; i < room_of.size(); ++i) cout << (i ? ", " : "") << room_of[i];
        cout << "]" << endl;
        cout << "  校验: 双指针 = " << sol.minMeetingRoomsBySweep(iv)
             << ", 暴力 = " << brute::minRooms(iv) << endl;
        assert(cnt == assigned);
        assert(checkAssignment(iv, room_of, cnt));
        assert(sol.minMeetingRoomsBySweep(iv) == cnt);
        assert(brute::minRooms(iv) == cnt);
    }

    mt19937 rng(20261102);
    for (int round = 0; round < 2000; ++round) {
        int n = rng() % 7;  // 0..6 个区间
        vector<vector<int>> iv;
        for (int i = 0; i < n; ++i) {
            int s = rng() % 10;
            int e = s + 1 + rng() % 5;
            iv.push_back({s, e});
        }
        auto copy = iv;
        int cnt = sol.minMeetingRooms(copy);
        vector<int> room_of;
        int assigned = sol.assignRooms(iv, room_of);
        int expect = brute::minRooms(iv);
        if (cnt != expect || assigned != expect || !checkAssignment(iv, room_of, cnt) ||
            sol.minMeetingRoomsBySweep(iv) != cnt) {
            cout << "MISMATCH round=" << round << " 会议: ";
            printIntervals(iv);
            cout << " greedy=" << cnt << " assign=" << assigned << " brute=" << expect << endl;
            return 1;
        }
    }
    cout << "随机对拍 2000 轮通过：贪心 / 分配方案 / 双指针 / 暴力 一致" << endl;
    return 0;
}
