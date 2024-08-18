#include "../include/fwd.h"

class Solution {
public:
    int robotSim(vector<int>& commands, vector<vector<int>>& obstacles) {
        int dx[4] = {0, 1, 0, -1};
        int dy[4] = {1, 0, -1, 0};

        int ans = 0;
        unordered_set<int> obstacleSet;
        for (auto& obstacle : obstacles) {
            obstacleSet.insert(obstacle[0] * 60001 + obstacle[1]);
        }
        int x = 0, y = 0, dir = 0;
        for (int command : commands) {
            if (command == -1) {
                dir = (dir + 1) % 4;
            } else if (command == -2) {
                dir = (dir + 3) % 4;
            } else {
                for (int i = 0; i < command; i++) {
                    int nx = x + dx[dir];
                    int ny = y + dy[dir];
                    if (obstacleSet.count(nx * 60001 + ny)) {
                        break;
                    }
                    x = nx;
                    y = ny;
                }
            }
            ans = max(ans, x * x + y * y);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> commands = {4, -1, 3};
    vector<vector<int>> obstacles = {{2, 4}};
    cout << solution.robotSim(commands, obstacles) << endl;
    return 0;
}