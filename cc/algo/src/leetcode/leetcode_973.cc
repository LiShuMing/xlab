#include "../include/fwd.h"

class Solution {
public:
    vector<vector<int>> kClosest(vector<vector<int>>& points, int k) {
        vector<vector<int>> result;
        sort(points.begin(), points.end(), [](const vector<int>& a, const vector<int>& b) {
            return a[0] * a[0] + a[1] * a[1] < b[0] * b[0] + b[1] * b[1];
        });
        for (int i = 0; i < k; i++) {
            result.push_back(points[i]);
        }
        return result;
    }
};
int main() {
    Solution solution;
    vector<vector<int>> points = {{1, 3}, {2, 2}, {2, 3}};
    int k = 1;
    vector<vector<int>> result = solution.kClosest(points, k);
    for (const auto& point : result) {
        cout << "(" << point[0] << ", " << point[1] << ")" << endl;
    }
    return 0;
}