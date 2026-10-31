#include "../include/fwd.h"

// class Solution {
// public:
//     int trap(vector<int>& height) {
//         int n = height.size();
//         vector<int> leftMax(n, 0);
//         vector<int> rightMax(n, 0);
//         leftMax[0] = height[0];
//         for (int i = 1; i < n; i++) {
//             leftMax[i] = max(leftMax[i - 1], height[i]);
//         }
//         rightMax[n - 1] = height[n - 1];
//         for (int i = n - 2; i >= 0; i--) {
//             rightMax[i] = max(rightMax[i + 1], height[i]);
//         }
//         int ans = 0;
//         for (int i = 0; i < n; i++) {
//             ans += min(leftMax[i], rightMax[i]) - height[i];
//         }
//         return ans;
//     }
// };

class Solution {
public:
    int trap(vector<int>& height) {
        // int, not size_t: an unsigned loop counter would never be < 0 and underflows
        // below zero instead of ending the backward scan.
        int n = static_cast<int>(height.size());
        if (n == 0) {
            return 0;
        }
        vector<int> li(n), hi(n);
        // find the left highest index
        li[0] = 0;
        for (int i = 1; i < n; i++) {
            if (height[i] > height[li[i-1]]) {
                li[i] = i;
            } else {
                li[i] = li[i-1];
            }
        }
        // find the right highest index
        hi[n-1] = n-1;
        for (int i = n - 2; i >= 0; i--) {
            if (height[i] > height[hi[i+1]]) {
                hi[i] = i;
            } else {
                hi[i] = hi[i+1];
            }
        }
        int ans = 0;
        for (int i = 0; i < n; i++) {
            ans += min(height[li[i]], height[hi[i]]) - height[i];
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> height = {0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1};
    int got = solution.trap(height);
    cout << got << endl;
    assert(got == 6);

    // edge cases: empty input traps nothing
    vector<int> empty;
    assert(solution.trap(empty) == 0);
    vector<int> single = {3};
    assert(solution.trap(single) == 0);

    cout << "all asserts passed" << endl;
    return 0;
}
