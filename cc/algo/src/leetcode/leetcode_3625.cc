#include "../include/fwd.h"

class Solution {
    public:
        int countTrapezoids(vector<vector<int>>& points) {
            unordered_map<double, map<double, int>> cnt1;
            unordered_map<int, map<double, int>> cnt2;
            int n = points.size();
            for (int i = 0; i < n; i++) {
                int x = points[i][0];
                int y = points[i][1];
                for (int j = 0; j < n; j++) {
                    if (i == j) {
                        continue;
                    }
                    int x2 = points[j][0];
                    int y2 = points[j][1];
                    double dx = x2 - x;
                    double dy = y2 - y;
                    double k = 1.0 * dy / dx;
                    double b = (y*dx - x*dy) / dx;
                    cnt1[k][b]++;
                    int mid = (x + x2) << 16 | (y + y2);
                    cnt2[mid][k]++;
                }
            }
            int ans = 0;
            for (auto& [_, m] : cnt1) {
                int s = 0;
                for (auto& [_, c] : m) {
                    ans += s * c;
                    s += c;
                }
            }
            for (auto& [_, m] : cnt2) {
                int s = 0;
                for (auto& [_, c] : m) {
                    ans -= s * c;
                    s += c;
                }
            }
            return ans;
        }
};

int main() {
    Solution solution;
    // case 1
    // string s = "aabca";
    // case 2
    vector<vector<int>> points = {{0, 0}, {1, 0}, {0, 1}, {1, 1}};
    int ans = solution.countTrapezoids(points);
    cout << ans << endl;
    return 0;
}