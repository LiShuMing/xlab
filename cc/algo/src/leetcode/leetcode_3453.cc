#include "../include/fwd.h"

class Solution {
public:
    double separateSquares(vector<vector<int> >& squares) {
        // use binary search to find the minimum distance
        int n = squares.size();
        

        double total_area = 0;
        double max_y = 0;
        for (int i = 0; i < n; i++) {
            double y = squares[i][1];
            double l = squares[i][2];
            total_area += l * l;
            max_y = max(max_y, y + l);
        }

        double left = 0;
        double right = max_y;
        double eps = 1e-5;
        while (abs(right - left) > eps) {
            double mid = left + (right - left) / 2;
            if (canSeparate(squares, total_area, max_y, mid)) {
                right = mid;
            } else {
                left = mid;
            }
        }
        return right;
    }
    bool canSeparate(vector<vector<int> >& squares, double total_area, int max_y, double distance) {
        // check if the squares can be separated by the distance
        int n = squares.size();
        double area = 0;
        for (int i = 0; i < n; i++) {
            int y = squares[i][1];
            int l = squares[i][2];
            if (y < distance) {
                double overlap = min((double)l, distance - y);
                area += overlap * l;
            }
        }
        return area >= total_area / 2;
    }
};

int main() {
    Solution solution;
    vector<vector<int> > squares;
    int arr1[] = {0, 0, 1};
    int arr2[] = {0, 1, 1};
    int arr3[] = {1, 0, 1};
    squares.push_back(vector<int>(arr1, arr1 + 3));
    squares.push_back(vector<int>(arr2, arr2 + 3));
    squares.push_back(vector<int>(arr3, arr3 + 3));
    cout << solution.separateSquares(squares) << endl;
    return 0;
}