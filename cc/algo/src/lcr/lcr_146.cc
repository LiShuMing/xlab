#include "../include/fwd.h"
class Solution {
public:
    vector<int> spiralArray(vector<vector<int> >& array) { 
        vector<int> ans; 
        int n = array.size();
        if (n == 0) return ans;
        int m = array[0].size();
        int top = 0, bottom = n - 1, left = 0, right = m - 1;
        
        while (top <= bottom && left <= right) {
            // left to right
            for (int i = left; i <= right; i++) {
                ans.push_back(array[top][i]);
            }
            top++;
            if (top > bottom) break;

            // top to bottom
            for (int i = top; i <= bottom; i++) {
                ans.push_back(array[i][right]);
            }
            right--;
            if (left > right) break;

            // right to left
            for (int i = right; i >= left; i--) {
                ans.push_back(array[bottom][i]);
            }
            bottom--;
            if (top > bottom) break;

            // bottom to top
            for (int i = bottom; i >= top; i--) {
                ans.push_back(array[i][left]);
            }
            left++;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    // vector<vector<int>> array = {{1, 2, 3}};
    int arr1[] = {1};
    int arr2[] = {2};
    int arr3[] = {3};
    vector<int> v1(arr1, arr1 + 1);
    vector<int> v2(arr2, arr2 + 1);
    vector<int> v3(arr3, arr3 + 1);
    vector<vector<int> > array;
    array.push_back(v1);
    array.push_back(v2);
    array.push_back(v3);
    // vector<vector<int>> array = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    vector<int> ans = solution.spiralArray(array);
    for (int i = 0; i < ans.size(); i++) {
        cout << ans[i] << ", ";
    }
    cout << endl;
    return 0;
}