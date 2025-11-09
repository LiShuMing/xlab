#include <numeric>
#include <functional>

#include "../include/fwd.h"
class Solution {
public:
    vector<int> processQueries(int c, vector<vector<int>>& connections,
                               vector<vector<int>>& queries) {
        vector<vector<int>> g(c + 1);
        for (auto& e : connections) {
            int x = e[0], y = e[1];
            g[x].push_back(y);
            g[y].push_back(x);
        }

        vector<int> belong(c + 1, -1);
        vector<priority_queue<int, vector<int>, greater<>>> heaps;
        priority_queue<int, vector<int>, greater<>> pq;

        std::function<void(int)> dfs;
        dfs = [&](int x) -> void {
            belong[x] = heaps.size(); 
            pq.push(x);
            for (int y : g[x]) {
                if (belong[y] < 0) {
                    dfs(y);
                }
            }
        };

        for (int i = 1; i <= c; i++) {
            if (belong[i] < 0) {
                dfs(i);
                heaps.emplace_back(move(pq));
            }
        }

        vector<int> ans;
        vector<int8_t> offline(c + 1);
        for (auto& q : queries) {
            int x = q[1];
            if (q[0] == 2) {
                offline[x] = true;
                continue;
            }
            if (!offline[x]) {
                ans.push_back(x);
                continue;
            }
            auto& h = heaps[belong[x]];
            while (!h.empty() && offline[h.top()]) {
                h.pop();
            }
            ans.push_back(h.empty() ? -1 : h.top());
        }
        return ans;
    }
};

int main() {
    Solution solution;
    int c = 5;
    vector<vector<int>> connections = {{1, 2}, {2, 3}, {3, 4}, {4, 5}};
    vector<vector<int>> queries = {{1, 3}, {2, 1}, {1, 1}, {2, 2}, {1, 2}};
    vector<int> ans = solution.processQueries(c, connections, queries);
    cout << "ans: ";
    for (auto& a : ans) {
        cout << a << " ";
    }
    cout << endl;
    return 0;
}