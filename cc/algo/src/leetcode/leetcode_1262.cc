#include "../include/fwd.h"

class Solution {
public:
    int maxSumDivThree(vector<int>& nums) {
        int n = nums.size();
        int memo[n][3];
        memset(memo, -1, sizeof(memo));
        
        function<int(int, int)> dfs = [&](int i, int sum) -> int {
            if (i < 0) return sum ? INT_MIN : 0;
            int& res = memo[i][sum];
            if (res != -1) return res;
            return res = max(dfs(i - 1, sum), dfs(i - 1, (sum + nums[i]) % 3) + nums[i]);
        };
        return dfs(n - 1, 0);
    }
};

int main() {
    Solution solution;
    vector<int> nums = {3, 6, 5, 1, 8};
    cout << "ans: " << solution.maxSumDivThree(nums) << endl;
    return 0;
}