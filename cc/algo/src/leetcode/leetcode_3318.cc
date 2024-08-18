#include "../include/fwd.h"

class Solution {
    public:
        vector<int> findXSum(vector<int>& nums, int k, int x) {
            int n = nums.size();
            std::vector<int> ans;
            for (int i = k; i <= n; i++) {
                std::unordered_map<int, int> cnt;
                // count the numbers in the window
                for (int j = i - k; j < i; j++) {
                    cnt[nums[j]] += 1;
                }
                // if the number of unique numbers is less than x, then we need to count all nums
                if (cnt.size() < x) {
                    int sum = 0;
                    for (auto&[k, v] : cnt) {
                        sum += k * v;
                    }
                    ans.push_back(sum);
                } else {
                    // choose the top x
                    std::vector<std::pair<int, int>> pairs(cnt.begin(), cnt.end());
                    std::sort(pairs.begin(), pairs.end(), [](const pair<int, int>& a, const pair<int, int>& b) {
                        if (a.second != b.second) {
                            return a.second > b.second;
                        }
                        return a.first > b.first;
                    });
                    int sum = 0;
                    int z = 0;
                    for (auto&[k, v] : pairs) {
                        if (z >= x) {
                            break;
                        }
                        sum += k * v;
                        z++;
                    }
                    ans.push_back(sum);
                }
            }
            return ans;
        }
};

int main() {
    Solution solution;
    vector<int> nums = {1,1,2,2,3,4,2,3};
    int k = 6;
    int x = 2;
    vector<int> ans = solution.findXSum(nums, k, x);
    printVector(ans);
    return 0;
}