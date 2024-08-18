#include "../include/fwd.h"

class Solution {
public:
    int snakesAndLadders(vector<vector<int>>& board) {
        int n = board.size();
        vector<int> cells(n * n + 1);
        int label = 1;
        vector<int> columns(n);
        for (int i = 0; i < n; i++) {
            columns[i] = i;
        }
        for (int i = n - 1; i >= 0; i--) {
            for (int j = 0; j < n; j++) {
                cells[label] = board[i][columns[j]];
                label++;
            }
            reverse(columns.begin(), columns.end());
        }
        vector<int> dist(n * n + 1, -1);
        queue<int> q;
        q.push(1);
        dist[1] = 0;
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            for (int v = u + 1; v <= min(u + 6, n * n); v++) {
                int target = cells[v] == -1 ? v : cells[v];
                if (dist[target] == -1) {
                    dist[target] = dist[u] + 1;
                    q.push(target);
                }
            }
        }
        if (dist[n * n] == -1) return -1;
        return dist[n * n];
    }
};

int main() {
    Solution solution;
    vector<vector<int>> board = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    cout << solution.snakesAndLadders(board) << endl;
    return 0;
}