#include "../include/fwd.h"
class Solution {
    public:
        int minOperations(vector<int>& nums) {
            stack<int> st;
            int ans = 0;
            for (int num : nums) {
                while (!st.empty() && st.top() > num) {
                    st.pop();
                    ans++;
                }

                if (st.empty() || st.top() < num) {
                    st.push(num);
                }
            }
            while (!st.empty()) {
                if (st.top() != 0) {
                    ans += 1;
                }
                st.pop();
            }
            return ans;
        }
};

int main() {
    Solution solution;
    {
            vector<int> nums = {1, 2, 1, 2, 1, 2};
            cout << "nums: ";
            printVector(nums);
            cout << "minOperations: " << solution.minOperations(nums) << endl;
    }
    {
        vector<int> nums = {0, 1, 0, 0, 1};
        cout << "nums: ";
        printVector(nums);
        cout << "minOperations: " << solution.minOperations(nums) << endl;
    }
    return 0;
}