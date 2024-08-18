#include "../include/fwd.h"

class Solution {
    public:
        int countTrapezoids(vector<vector<int>>& points) {
            const int MOD = 1e9 + 7;
            unordered_map<int, int> x_count;
            // group by y
            for (auto& point : points) {
                x_count[point[1]]++;
            }
            // count the number of points in each x
            long long ans = 0;
            long long sum = 0;
            for (auto& [y, count] : x_count) {
                long long tmp = (long long)count * (count - 1) / 2;
                ans += sum * tmp;
                sum += tmp;
            }
            return ans % MOD;
        }
    };

int main() {
    Solution solution;
    // case 1
    // vector<vector<int>> intervals = {{1,3}, {3,7}, {4,9}, {8,9}};
    vector<vector<int>> points = {{1,0},{2,0},{3,0},{2,2},{3,2}};
    int ans = solution.countTrapezoids(points);
    cout << ans << endl;
    return 0;
}