#include "../include/fwd.h"

class Solution {
public:
    // TODO: use hash map to optimize the time complexity
    int lengthOfLongestSubstring(string s) {
        unordered_set<char> st;
        int n = s.size();

        int ans = 0;
        int l = 0;
        for (int i = 0; i < n; i++) {
            if (st.find(s[i]) != st.end()) {
                while (s[l] != s[i]) {
                    st.erase(s[l]);
                    l++;
                }
                st.erase(s[l]);
                l++;
            }
            st.insert(s[i]);
            ans = max(ans, i - l + 1);
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