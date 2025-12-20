#include "../include/fwd.h"
class Solution {
public:
    int kthSmallest(vector<vector<int>>& matrix, int k) {
        struct Point {
            int x, y;
            int val;
            Point(int x, int y, int val) : x(x), y(y), val(val) {}
            bool operator>(const Point& other) const {
                return val > other.val;
            }
        };
        // use a min heap to store the points
        priority_queue<Point, vector<Point>, greater<Point>> pq;
        int n = matrix.size();
        for (int i = 0; i < n; i++) {
            pq.push(Point(i, 0, matrix[i][0]));
        }
        for (int i = 0; i < k - 1; i++) {
            Point p = pq.top();
            pq.pop();
            if (p.y < n - 1) {
                pq.push(Point(p.x, p.y + 1, matrix[p.x][p.y + 1]));
            }
        }
        return pq.top().val;
    }

    // use binary search to find the kth smallest element
    int kthSmallest2(vector<vector<int>>& matrix, int k) {
        int n = matrix.size();
        int left = matrix[0][0];
        int right = matrix[n-1][n-1];
        while (left < right) {
            int mid = left + (right - left) / 2;
            int count = 0;
            for (int i = 0; i < n; i++) {
                count += upper_bound(matrix[i].begin(), matrix[i].end(), mid) - matrix[i].begin();
            }
            if (count < k) {
                left = mid + 1;
            } else {
                right = mid;
            }
        }
        return left;
    }
};
int main() {
    Solution solution;
    vector<vector<int>> matrix = {{1, 5, 9}, {10, 11, 13}, {12, 13, 15}};
    int k = 8;
    cout << solution.kthSmallest2(matrix, k) << endl;
    return 0;
}