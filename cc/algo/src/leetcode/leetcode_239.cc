#include "../include/fwd.h"

class Solution {
public:
    vector<int> maxSlidingWindow(vector<int>& nums, int k) {
        int n = nums.size();
        vector<int> ans;
        deque<int> dq;
        for (int i = 0; i < n; i++) {
            // remove the element if it is out of the window
            if (!dq.empty() && dq.front() == i - k) {
                dq.pop_front();
            }
            // ensure the deque is in descending order
            while (!dq.empty() && nums[dq.back()] < nums[i]) {
                dq.pop_back();
            }
            // push the current element to the deque
            dq.push_back(i);
            // push the max element to the answer
            if (i >= k - 1) {
                ans.push_back(nums[dq.front()]);
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> nums = {1, 3, -1, -3, 5, 3, 6, 7};
    int k = 3;
    vector<int> ans = solution.maxSlidingWindow(nums, k);
    printVector(ans);
    return 0;
}