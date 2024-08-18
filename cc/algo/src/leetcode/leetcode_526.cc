#include "../include/fwd.h"

class Solution {
public:
    int countArrangement(int n) {
        vector<int> nums(n);
        for (int i = 0; i < n; i++) {
            nums[i] = i + 1;
        }
        int ans = 0;
        backtrack(nums, 0, ans);
        return ans;
    }

private:
    void backtrack(vector<int>& nums, int pos, int& ans) {
        if (pos == nums.size()) {
            ans++;
            return;
        }
        
        for (int i = pos; i < nums.size(); i++) {
            // Check if nums[i] can be placed at position pos
            // Condition: nums[i] % (pos + 1) == 0 || (pos + 1) % nums[i] == 0
            if (nums[i] % (pos + 1) == 0 || (pos + 1) % nums[i] == 0) {
                swap(nums, pos, i);
                backtrack(nums, pos + 1, ans);
                swap(nums, pos, i);  // Backtrack
            }
        }
    }

    void swap(vector<int>& nums, int i, int j) {
        int temp = nums[i];
        nums[i] = nums[j];
        nums[j] = temp;
    }
};

int main() {
    Solution solution;
    int n = 10;
    cout << solution.countArrangement(n) << endl;
    return 0;
}