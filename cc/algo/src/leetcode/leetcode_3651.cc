#include "../include/fwd.h"
#include <queue>
#include <vector>
#include <limits>
#include <tuple>

/**
 * Given m x n grid and integer k.
 * Start at (0, 0), goal is (m-1, n-1).
 * Normal move (right/down): cost = target cell value
 * Teleport: from (i,j) to any (x,y) with grid[x][y] <= grid[i][j], cost = 0, max k times
 * Return minimum total cost.
 */
class Solution {
public:
    int minCost(vector<vector<int>>& grid, int k) {
        int m = grid.size();
        int n = grid[0].size();

        // dp[x][y][t] = minimum cost to reach (x,y) using exactly t teleports
        const int INF = std::numeric_limits<int>::max() / 2;
        std::vector<std::vector<std::vector<int>>> dp(
            m, std::vector<std::vector<int>>(n, std::vector<int>(k + 1, INF)));

        // Priority queue: (cost, x, y, teleports_used)
        using State = std::tuple<int, int, int, int>;
        std::priority_queue<State, std::vector<State>, std::greater<State>> pq;

        dp[0][0][0] = 0;
        pq.emplace(0, 0, 0, 0);

        while (!pq.empty()) {
            auto [cost, x, y, used] = pq.top();
            pq.pop();

            if (cost != dp[x][y][used]) continue;
            if (x == m - 1 && y == n - 1) return cost;

            // Normal moves: right and down
            const int dx[2] = {0, 1};
            const int dy[2] = {1, 0};

            for (int dir = 0; dir < 2; ++dir) {
                int nx = x + dx[dir];
                int ny = y + dy[dir];
                if (nx >= m || ny >= n) continue;
                int ncost = cost + grid[nx][ny];
                if (ncost < dp[nx][ny][used]) {
                    dp[nx][ny][used] = ncost;
                    pq.emplace(ncost, nx, ny, used);
                }
            }

            // Teleport: from (x,y) to any cell with value <= grid[x][y]
            if (used < k) {
                int threshold = grid[x][y];
                for (int i = 0; i < m; ++i) {
                    for (int j = 0; j < n; ++j) {
                        if (grid[i][j] <= threshold && !(i == x && j == y)) {
                            if (cost < dp[i][j][used + 1]) {
                                dp[i][j][used + 1] = cost;
                                pq.emplace(cost, i, j, used + 1);
                            }
                        }
                    }
                }
            }
        }

        // Should not reach here for valid inputs
        return INF;
    }
};

int main() {
    Solution solution;
    vector<vector<int>> grid = {{1,1,1,1},{2,2,2,2},{1,1,1,1},{2,2,2,2}};
    int k = 3;
    cout << solution.minCost(grid, k) << endl;
    return 0;
}