#include "../include/fwd.h"
class Solution {
    public:
        int findKthLargest(vector<int>& nums, int k) {
            priority_queue<int, vector<int>, greater<int>> pq;
            for (int num : nums) {
                pq.push(num);
                if (pq.size() > k) {
                    pq.pop();
                }
            }
            return pq.top();
        }
    };

int main() {
    Solution solution;
    vector<int> nums = {3, 2, 1, 5, 6, 4};
    int k = 2;
    cout << solution.findKthLargest(nums, k) << endl;
    return 0;
}