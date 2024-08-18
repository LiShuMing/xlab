#include "../include/fwd.h"
class Solution {
    public:
        int subarraySum(vector<int>& nums, int k) {
            int n = nums.size();
            int ans = 0;
            int sum = 0;
            unordered_map<int, int> freq;
            // freq[0] = 1 because the sum of 0 is 0
            freq[0] = 1;
            for (int i = 0; i < n; i++) {
                sum += nums[i];
                if (freq.find(sum - k) != freq.end()) {
                    ans += freq[sum - k];
                }
                freq[sum]++;
            }
            return ans;
        }
    };

int main() {
    Solution solution;
    vector<int> nums = {1, 1, 1};
    int k = 2;
    cout << solution.subarraySum(nums, k) << endl;
    return 0;
}