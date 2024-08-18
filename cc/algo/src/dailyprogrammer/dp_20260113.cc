#include "../include/fwd.h"
/**
* 有 𝑁 头牛从左到右排成一排，每头牛有一个高度 ℎ𝑖，
* 设左数第 𝑖 头牛与「它右边第一头高度 ≥ℎ𝑖」的牛之间有 𝑐𝑖 头牛，试求 ∑𝑁𝑖=1𝑐𝑖．
* 
* 输入：
* 第一行输入一个整数 𝑁，表示牛的数量。
* 第二行输入 𝑁 个整数，表示每头牛的高度。
* 
* 输出：
* 输出一个整数，表示 ∑𝑁𝑖=1𝑐𝑖．
 */

class Solution {
public:
    /**
    * Solve the summation of ci using a monotonic stack.
    * Time Complexity: O(N) - Each cow is pushed and popped at most once.
    * Space Complexity: O(N) - To store the stack and heights.
    */
    long long solve_cow_visibility(int n, const std::vector<int>& heights) {
        stack<int> st;
        vector<int> ans(n, 0);
        for (int i = 0; i < n; i++) {
            while (!st.empty() && heights[st.top()] < heights[i]) {
                ans[st.top()] = i - st.top() - 1;
                st.pop();
            }
            st.push(i);
        }
        return accumulate(ans.begin(), ans.end(), 0LL);
    }
};

int main() {
    Solution solution;
    int n = 5;
    vector<int> heights = {1, 2, 3, 4, 5};
    cout << solution.solve_cow_visibility(n, heights) << endl;
    return 0;
}