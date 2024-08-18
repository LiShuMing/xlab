#include "../include/fwd.h"
class Solution {
public:
    int wardrobeFinishing(int m, int n, int cnt) {
        vector<vector<bool>> visited(m, vector<bool>(n, false));
        return dfs(m, n, cnt, 0, 0, visited);
    }
    int dfs(int m, int n, int cnt, int i, int j, vector<vector<bool>>& visited) {
        if (cnt == 0) return 1;
        if (i < 0 || i >= m || j < 0 || j >= n || visited[i][j] || !valid(i, j, cnt)) {
            return 0;
        }
        if (visited[i][j]) return 0;
        visited[i][j] = true;
        vector<pair<int, int>> dirs = {{1, 0}, {0, 1}, {-1, 0}, {0, -1}};
        int ans = 1;
        for (auto& dir : dirs) {
            ans += dfs(m, n, cnt, i + dir.first, j + dir.second, visited);
        }
        return ans;
    }
    // check if the sum of the digits of i and j is less than or equal to k
    bool valid(int i, int j, int k) { return i / 10 + i % 10 + j / 10 + j % 10 <= k; }
};
int main() {
    Solution solution;
    cout << solution.wardrobeFinishing(2, 2, 2) << endl;
    return 0;
}