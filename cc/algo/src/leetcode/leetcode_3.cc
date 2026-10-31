#include "../include/fwd.h"

// class Solution {
// public:
//     // TODO: use hash map to optimize the time complexity
//     // idea: 滑动窗口
//     int lengthOfLongestSubstring(string s) {
//         unordered_set<char> st;
//         int n = s.size();

//         int ans = 0;
//         int l = 0;
//         for (int i = 0; i < n; i++) {
//             if (st.find(s[i]) != st.end()) {
//                 while (s[l] != s[i]) {
//                     st.erase(s[l]);
//                     l++;
//                 }
//                 st.erase(s[l]);
//                 l++;
//             }
//             st.insert(s[i]);
//             ans = max(ans, i - l + 1);
//         }
//         return ans;
//     }
// };

class Solution {
public:
    // 滑动窗口 + last 数组：左边界直接跳到上次出现位置的右边，不再逐个 erase
    int lengthOfLongestSubstring(string s) {
        vector<int> last(128, -1);  // last[c] = 字符 c 上一次出现的下标
        int ans = 0;
        int l = -1;  // 窗口左边界的前一个位置（窗口是 (l, i]）
        for (int i = 0; i < (int)s.size(); i++) {
            int c = (unsigned char)s[i];
            l = max(l, last[c]);  // s[i] 若在窗口内出现过，左边界直接跳到它后面
            last[c] = i;
            ans = max(ans, i - l);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    string s = "dvdf";
    // string s = "abcabcbb";
    cout << solution.lengthOfLongestSubstring(s) << endl;
    return 0;
}
