#include "../include/fwd.h"

class Solution {
public:
    int intersectionSizeTwo(vector<vector<int>>& intervals) {
        sort(intervals.begin(), intervals.end(), [](const vector<int>& a, const vector<int>& b) {
            return a[1] == b[1] ? a[0] > b[0] : a[1] < b[1];
        });
        int ans = 0;
        int s = -1, e = -1;
        for (auto& interval : intervals) {
            // cout << "interval: " << interval[0] << " " << interval[1] << endl;
            int a = interval[0], b = interval[1];
            if (a <= s) {
                continue;
            }
            if (a > e) {
                ans += 2;
                s = b - 1;
                e = b;
            } else {
                ans++;
                s = e;
                e = b;
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    // case 1
    // vector<vector<int>> intervals = {{1,3}, {3,7}, {4,9}, {8,9}};
    vector<vector<int>> intervals = {{1,3}, {3,7}, {5, 7}, {7, 8}};
    int ans = solution.intersectionSizeTwo(intervals);
    cout << ans << endl;
    return 0;
}